import io
import wave
import logging
import asyncio
import httpx
import numpy as np
import sounddevice as sd
from config import settings

logger = logging.getLogger("tts_player")

class TTSAudioPlayer:
    def __init__(self, output_device_name: str | int = None):
        self.output_device = None
        target = output_device_name or getattr(settings, "output_device", None)
        
        if target is not None:
            try:
                # Si es entero directo
                if isinstance(target, int) or (isinstance(target, str) and target.isdigit()):
                    self.output_device = int(target)
                else:
                    devices = sd.query_devices()
                    for idx, d in enumerate(devices):
                        if str(target).lower() in d['name'].lower() and d['max_output_channels'] > 0:
                            self.output_device = idx
                            logger.info(f"Dispositivo de salida seleccionado: [{idx}] {d['name']}")
                            break
            except Exception as e:
                logger.warning(f"Error resolviendo dispositivo de salida: {e}")

        self.http_client = httpx.AsyncClient(timeout=10.0)

    async def generate_voicebox_speech(self, text: str) -> np.ndarray | None:
        if not text:
            return None
        url = f"{settings.voicebox_url}/generate/stream"
        payload = {
            "text": text,
            "language": settings.target_lang,
        }
        if settings.voicebox_profile_id:
            payload["profile_id"] = settings.voicebox_profile_id

        try:
            res = await self.http_client.post(url, json=payload)
            if res.status_code == 200:
                with wave.open(io.BytesIO(res.content), 'rb') as wf:
                    n_channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    framerate = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())
                    
                    if sampwidth == 2:
                        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    else:
                        data = np.frombuffer(frames, dtype=np.float32)
                        
                    if n_channels > 1:
                        data = data.reshape(-1, n_channels)[:, 0]
                    return data
            else:
                logger.debug(f"Voicebox no devolvio audio ({res.status_code})")
                return None
        except Exception as e:
            logger.debug(f"Voicebox no disponible en {url}: {e}")
            return None

    def play_audio(self, audio_data: np.ndarray, sample_rate: int = 16000, blocking: bool = False):
        if audio_data is None or len(audio_data) == 0:
            return

        try:
            sd.play(audio_data, samplerate=sample_rate, device=self.output_device, blocking=blocking)
        except Exception as e:
            logger.warning(f"Error reproduciendo audio: {e}")

    async def play_voice_or_duck(self, translated_text: str, original_chunk: np.ndarray = None, sample_rate: int = 16000):
        tts_audio = await self.generate_voicebox_speech(translated_text)
        if tts_audio is None or len(tts_audio) == 0:
            return

        mode = settings.operation_mode
        if mode in ["voice_ducking", "all"] and original_chunk is not None:
            attenuated_orig = original_chunk * settings.ducking_background_volume
            
            len_tts = len(tts_audio)
            len_orig = len(attenuated_orig)
            max_len = max(len_tts, len_orig)
            
            mixed = np.zeros(max_len, dtype=np.float32)
            mixed[:len_orig] += attenuated_orig
            mixed[:len_tts] += tts_audio
            
            peak = np.max(np.abs(mixed))
            if peak > 1.0:
                mixed /= peak

            self.play_audio(mixed, sample_rate=sample_rate)
        else:
            self.play_audio(tts_audio, sample_rate=sample_rate)

    async def close(self):
        await self.http_client.aclose()
