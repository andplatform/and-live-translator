import io
import time
import logging
import numpy as np
import scipy.io.wavfile as wavfile
from config import settings

logger = logging.getLogger("stt_translator")

class STTTranslator:
    def __init__(self):
        self.groq_client = None
        
        if settings.groq_api_key:
            try:
                from groq import AsyncGroq
                self.groq_client = AsyncGroq(api_key=settings.groq_api_key)
                logger.info("Cliente Groq activado para STT y Traduccion ultrarrapida (<150ms).")
            except Exception as e:
                logger.warning(f"No se pudo inicializar Groq: {e}")

    def _audio_to_wav_bytes(self, audio_data: np.ndarray, sample_rate: int = 16000) -> bytes:
        scaled = np.int16(audio_data / np.max(np.abs(audio_data) + 1e-6) * 32767)
        buffer = io.BytesIO()
        wavfile.write(buffer, sample_rate, scaled)
        buffer.seek(0)
        return buffer.read()

    async def transcribe(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> str:
        if len(audio_chunk) < sample_rate * 0.4:
            return ""

        wav_bytes = self._audio_to_wav_bytes(audio_chunk, sample_rate)
        glossary_prompt = "Glosario y contexto de programa: " + ", ".join(settings.glossary)

        if self.groq_client:
            try:
                transcription = await self.groq_client.audio.transcriptions.create(
                    file=("audio.wav", wav_bytes, "audio/wav"),
                    model="whisper-large-v3-turbo",
                    prompt=glossary_prompt,
                    language=settings.source_lang if settings.source_lang != "auto" else None,
                    response_format="text"
                )
                return str(transcription).strip()
            except Exception as e:
                logger.error(f"[STT Groq Error]: {e}")

        return ""

    async def translate(self, text: str) -> str:
        if not text or len(text.strip()) == 0:
            return ""

        if settings.source_lang == settings.target_lang:
            return text

        system_prompt = (
            "Eres un interprete simultaneo de television en directo para un canal en espanol. "
            "Traduce la frase al espanol de forma natural, directa y breve para rotulos televisivos y doblaje. "
            "Respeta escrupulosamente nombres propios, marcas y terminos tecnicos. "
            "IMPORTANTE: Devuelve UNICA Y EXCLUSIVAMENTE la frase traducida, sin explicaciones, sin comillas ni notas adicionales.\n"
            f"Glosario: {', '.join(settings.glossary)}"
        )

        if self.groq_client:
            try:
                response = await self.groq_client.chat.completions.create(
                    model="groq/compound",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    temperature=0.1,
                    max_tokens=150,
                )
                raw = response.choices[0].message.content
                if raw:
                    # Normalizar espacios no separables tipograficos a espacios estándar
                    clean = (
                        raw.replace('\u202f', ' ')
                           .replace('\xa0', ' ')
                           .strip()
                           .strip('\"')
                           .strip('\'')
                           .strip('*')
                    )
                    return clean
            except Exception as e:
                logger.warning(f"[Translation Groq Error]: {e}")

        return text

    async def process_chunk(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> dict:
        t0 = time.perf_counter()
        original_text = await self.transcribe(audio_chunk, sample_rate)
        if not original_text:
            return {"original": "", "translated": "", "latency_ms": 0}

        translated_text = await self.translate(original_text)
        t1 = time.perf_counter()
        latency_ms = int((t1 - t0) * 1000)

        logger.info(f"[{latency_ms}ms] '{original_text}' -> '{translated_text}'")
        return {
            "original": original_text,
            "translated": translated_text,
            "latency_ms": latency_ms
        }
