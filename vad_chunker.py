import asyncio
import collections
import logging
import numpy as np
import sounddevice as sd

logger = logging.getLogger("vad_chunker")

class VADAudioChunker:
    """
    Captura audio en tiempo real y segmenta la voz mediante deteccion de energia / VAD.
    Entrega trozos completos de frase coincidiendo con las pausas de respiracion del orador.
    """
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        silence_threshold_db: float = -42.0,
        min_silence_duration_ms: int = 400,
        min_speech_duration_ms: int = 600,
        max_chunk_duration_s: float = 6.0,
        device_index: int | str = None,
        vu_callback = None
    ):
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * (frame_duration_ms / 1000.0))
        self.silence_threshold_linear = 10 ** (silence_threshold_db / 20.0)
        self.min_silence_frames = int(min_silence_duration_ms / frame_duration_ms)
        self.min_speech_frames = int(min_speech_duration_ms / frame_duration_ms)
        self.max_chunk_frames = int((max_chunk_duration_s * 1000) / frame_duration_ms)
        
        self.device_index = self._parse_device_index(device_index)
        self.vu_callback = vu_callback

        self._queue = asyncio.Queue()
        self._loop = None
        self._is_running = False
        self._stream = None

    @staticmethod
    def _parse_device_index(dev):
        if dev is None or str(dev).strip() == "" or str(dev).lower() in ["default", "none", "null"]:
            return None
        try:
            return int(dev)
        except (ValueError, TypeError):
            return str(dev)

    @staticmethod
    def list_audio_devices() -> dict:
        """Devuelve listas de dispositivos de entrada y salida disponibles en el sistema."""
        inputs = []
        outputs = []
        try:
            devices = sd.query_devices()
            for idx, d in enumerate(devices):
                item = {
                    "id": idx,
                    "name": d["name"],
                    "hostapi": d["hostapi"],
                    "max_inputs": d["max_input_channels"],
                    "max_outputs": d["max_output_channels"],
                    "default_samplerate": d["default_samplerate"]
                }
                if d["max_input_channels"] > 0:
                    inputs.append(item)
                if d["max_output_channels"] > 0:
                    outputs.append(item)
        except Exception as e:
            logger.warning(f"Error enumerando dispositivos de audio: {e}")
        return {"inputs": inputs, "outputs": outputs}

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.debug(f"[Audio Status]: {status}")
        audio_mono = indata[:, 0].copy() if indata.ndim > 1 else indata.flatten().copy()
        
        if self._loop and self._is_running:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, audio_mono)
            if self.vu_callback:
                rms = float(np.sqrt(np.mean(audio_mono ** 2))) if len(audio_mono) > 0 else 0.0
                vu_level = min(100, int(rms * 400)) # escala 0 a 100
                self._loop.call_soon_threadsafe(self.vu_callback, vu_level)

    async def start(self):
        self._loop = asyncio.get_running_loop()
        self._is_running = True
        
        dev = self.device_index
        if isinstance(dev, str) and dev:
            try:
                devices = sd.query_devices()
                for idx, d in enumerate(devices):
                    if dev.lower() in d['name'].lower() and d['max_input_channels'] > 0:
                        dev = idx
                        logger.info(f"Dispositivo de entrada resuelto por nombre: [{idx}] {d['name']}")
                        break
            except Exception as e:
                logger.warning(f"Error buscando dispositivo de audio: {e}")
                dev = None

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.frame_size,
                device=dev,
                channels=1,
                dtype='float32',
                callback=self._audio_callback
            )
            self._stream.start()
            logger.info(f"Stream de captura iniciado en dispositivo [{dev or 'Default'}] a {self.sample_rate} Hz")
        except Exception as e:
            logger.warning(f"No se pudo iniciar stream de audio fisico ({e}). El sistema continuara en modo API/Web.")
            self._stream = None

    async def stop(self):
        self._is_running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    async def switch_device(self, new_device_index: int | str | None):
        """Permite cambiar el dispositivo de audio en caliente sin reiniciar el servidor."""
        logger.info(f"Cambiando dispositivo de audio a: {new_device_index}")
        await self.stop()
        self.device_index = self._parse_device_index(new_device_index)
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break
        await self.start()

    async def speech_chunks(self):
        buffer = []
        speech_frames = 0
        silence_frames = 0
        in_speech = False

        while self._is_running:
            try:
                frame = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            rms = np.sqrt(np.mean(frame ** 2)) if len(frame) > 0 else 0.0
            is_voice = rms > self.silence_threshold_linear

            if is_voice:
                in_speech = True
                silence_frames = 0
                speech_frames += 1
                buffer.append(frame)
            else:
                if in_speech:
                    silence_frames += 1
                    buffer.append(frame)

                    if silence_frames >= self.min_silence_frames or len(buffer) >= self.max_chunk_frames:
                        if speech_frames >= self.min_speech_frames:
                            full_chunk = np.concatenate(buffer)
                            yield full_chunk
                        
                        buffer = []
                        speech_frames = 0
                        silence_frames = 0
                        in_speech = False
