import io
import wave
import logging
import asyncio
import httpx
import numpy as np
import sounddevice as sd
from scipy import signal
from config import settings

logger = logging.getLogger("tts_player")

# Voces neuronales de calidad broadcast por idioma
DEFAULT_VOICES = {
    "es": "es-ES-AlvaroNeural",
    "en": "en-US-AndrewNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-DiegoNeural",
    "pt": "pt-BR-AntonioNeural"
}

class TTSAudioPlayer:
    def __init__(self, output_device_name: str | int = None):
        self.output_device = None
        target = output_device_name or getattr(settings, "output_device", None)
        
        if target is not None:
            try:
                if isinstance(target, int) or (isinstance(target, str) and target.isdigit()):
                    self.output_device = int(target)
                else:
                    devices = sd.query_devices()
                    for idx, d in enumerate(devices):
                        if str(target).lower() in d['name'].lower() and d['max_output_channels'] > 0:
                            self.output_device = idx
                            logger.info(f"Dispositivo de salida de doblaje: [{idx}] {d['name']}")
                            break
            except Exception as e:
                logger.warning(f"Error resolviendo dispositivo de salida: {e}")

        self.http_client = httpx.AsyncClient(timeout=10.0)

    async def generate_edge_tts_speech(self, text: str, lang: str = "es") -> tuple[np.ndarray | None, int]:
        """Genera voz neuronal sintética con edge-tts (ultra-baja latencia, calidad broadcast)."""
        if not text:
            return None, 16000

        voice = DEFAULT_VOICES.get(lang, "es-ES-AlvaroNeural")
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            if not audio_data:
                return None, 16000

            # Decodificar el audio MP3/PCM devuelto por edge-tts
            # edge-tts devuelve mp3 por defecto (audio/mpeg). Lo decodificamos a float32 con miniaudio o scipy/soundfile
            # Intentar decodificar con soundfile o decodificador interno
            try:
                import soundfile as sf
                with io.BytesIO(audio_data) as f:
                    data, sr = sf.read(f, dtype='float32')
                    if data.ndim > 1:
                        data = data[:, 0]
                    return data, sr
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"[Edge-TTS Error]: {e}")

        return None, 16000

    async def generate_voicebox_speech(self, text: str) -> tuple[np.ndarray | None, int]:
        """Consulta Voicebox local (127.0.0.1:17493) si esta corriendo."""
        if not text:
            return None, 16000

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
                    return data, framerate
        except Exception:
            pass

        return None, 16000

    async def synthesize_speech(self, text: str, lang: str = "es") -> tuple[np.ndarray | None, int]:
        """Estrategia de doblaje en cascada: Voicebox local -> Edge-TTS neuronal."""
        # 1. Intentar Voicebox si esta disponible
        data, sr = await self.generate_voicebox_speech(text)
        if data is not None and len(data) > 0:
            return data, sr

        # 2. Respaldo directo: Edge-TTS
        data, sr = await self.generate_edge_tts_speech(text, lang=lang)
        if data is not None and len(data) > 0:
            return data, sr

        return None, 16000

    def play_audio(self, audio_data: np.ndarray, sample_rate: int = 48000, blocking: bool = False):
        if audio_data is None or len(audio_data) == 0:
            return

        try:
            sd.play(audio_data, samplerate=sample_rate, device=self.output_device, blocking=blocking)
        except Exception as e:
            logger.warning(f"Error reproduciendo audio: {e}")

    async def play_voice_or_duck(self, translated_text: str, original_chunk: np.ndarray = None, orig_sample_rate: int = 16000):
        tts_audio, tts_sr = await self.synthesize_speech(translated_text, lang=settings.target_lang)
        if tts_audio is None or len(tts_audio) == 0:
            return

        # Frecuencia estandar de broadcast (48 kHz)
        TARGET_SR = 48000

        # Resamplear audio sintetizado a 48kHz si es necesario
        if tts_sr != TARGET_SR:
            num_samples = int(len(tts_audio) * (TARGET_SR / tts_sr))
            tts_resampled = signal.resample(tts_audio, num_samples).astype(np.float32)
        else:
            tts_resampled = tts_audio

        mode = settings.operation_mode
        if mode in ["voice_ducking", "all"] and original_chunk is not None and len(original_chunk) > 0:
            # Resamplear el chunk original del ponente a 48kHz
            if orig_sample_rate != TARGET_SR:
                num_samples_orig = int(len(original_chunk) * (TARGET_SR / orig_sample_rate))
                orig_resampled = signal.resample(original_chunk, num_samples_orig).astype(np.float32)
            else:
                orig_resampled = original_chunk

            # Atenuar voz original con ducking (-16dB aprox)
            attenuated_orig = orig_resampled * settings.ducking_background_volume
            
            len_tts = len(tts_resampled)
            len_orig = len(attenuated_orig)
            max_len = max(len_tts, len_orig)
            
            mixed = np.zeros(max_len, dtype=np.float32)
            mixed[:len_orig] += attenuated_orig
            mixed[:len_tts] += tts_resampled
            
            # Limitador suave para evitar distorsión
            peak = np.max(np.abs(mixed))
            if peak > 0.95:
                mixed = mixed / peak * 0.95

            self.play_audio(mixed, sample_rate=TARGET_SR)
        else:
            self.play_audio(tts_resampled, sample_rate=TARGET_SR)

    async def close(self):
        await self.http_client.aclose()
