import io
import re
import time
import logging
import asyncio
import numpy as np
import scipy.io.wavfile as wavfile
from config import settings

logger = logging.getLogger("stt_translator")

LANGUAGE_NAMES = {
    "es": "español",
    "en": "inglés",
    "fr": "francés",
    "de": "alemán",
    "it": "italiano",
    "pt": "portugués",
    "zh": "chino mandarín",
    "ja": "japonés",
    "ru": "ruso",
    "ar": "árabe",
    "nl": "holandés"
}

def clean_translation_text(raw: str) -> str:
    """Elimina metadatos de modelos de razonamiento (Groq/Qwen/Llama), etiquetas think y prefijos."""
    if not raw:
        return ""

    # 1. Eliminar etiquetas <think>...</think> si existen
    cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)

    # 2. Cortar si el modelo añade secciones de razonamiento o notas
    lower_c = cleaned.lower()
    cut_tokens = [
        "**raisonnement**", "**explication**", "**explicación**", 
        "**reasoning**", "**notas**", "**notes**", "raisonnement:", "explication:"
    ]
    for token in cut_tokens:
        idx = lower_c.find(token)
        if idx != -1:
            cleaned = cleaned[:idx]
            lower_c = cleaned.lower()

    # 3. Extraer la línea de traducción real
    lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
    candidate = ""
    for line in lines:
        clean_line = re.sub(r'^(\*\*|#)*\s*(traduction|traducción|translation|übersetzung)\s*(\*\*|#)*\s*[:\-\*]*\s*', '', line, flags=re.IGNORECASE).strip()
        if clean_line and not clean_line.startswith("**") and not clean_line.startswith("#"):
            candidate = clean_line
            break

    if not candidate and lines:
        candidate = lines[0]

    # 4. Normalizar espacios tipográficos no separables (evita fallos de render en broadcast)
    final = (
        candidate.replace('\u202f', ' ')
                 .replace('\xa0', ' ')
                 .strip()
                 .strip('\"')
                 .strip('\'')
                 .strip('*')
    )
    return final

class STTTranslator:
    def __init__(self):
        self.groq_client = None
        self._last_partial_text = ""
        self._last_partial_translations = {}
        
        if settings.groq_api_key:
            try:
                from groq import AsyncGroq
                self.groq_client = AsyncGroq(api_key=settings.groq_api_key)
                logger.info("Cliente Groq activado para STT y Traduccion ultrarrapida (<150ms).")
            except Exception as e:
                logger.warning(f"No se pudo inicializar Groq: {e}")

    def reset_partial_cache(self):
        self._last_partial_text = ""
        self._last_partial_translations = {}

    def _audio_to_wav_bytes(self, audio_data: np.ndarray, sample_rate: int = 16000) -> bytes:
        scaled = np.clip(audio_data * 32767.0, -32768, 32767).astype(np.int16)
        buffer = io.BytesIO()
        wavfile.write(buffer, sample_rate, scaled)
        buffer.seek(0)
        return buffer.read()

    async def transcribe(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> str:
        if len(audio_chunk) < sample_rate * 0.35:
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

    async def translate_to_lang(self, text: str, target_lang: str) -> str:
        if not text or len(text.strip()) == 0:
            return ""

        if settings.source_lang == target_lang:
            return text

        lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)
        system_prompt = (
            f"Eres un interprete simultaneo de television en directo. "
            f"Traduce la frase al {lang_name} de forma natural, directa y breve para rotulos televisivos y subtitulos. "
            "Respeta escrupulosamente nombres propios, marcas y terminos tecnicos. "
            "REGLA ESTRICTA: Devuelve UNICA Y EXCLUSIVAMENTE una sola linea con la frase traducida. "
            "Prohibido incluir notas, comentarios, razonamientos o encabezados como 'Traduction:'.\n"
            f"Glosario: {', '.join(settings.glossary)}"
        )

        if self.groq_client:
            try:
                response = await self.groq_client.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    temperature=0.0,
                    max_tokens=150,
                )
                raw = response.choices[0].message.content
                if raw:
                    return clean_translation_text(raw)
            except Exception as e:
                logger.warning(f"[Translation Groq Error {target_lang}]: {e}")

        return text

    async def translate_multi(self, text: str, target_langs: list[str]) -> dict[str, str]:
        """Traduce concurrentemente la misma frase a múltiples idiomas en paralelo."""
        if not text:
            return {}

        tasks = [self.translate_to_lang(text, lang) for lang in target_langs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for lang, res in zip(target_langs, results):
            if isinstance(res, str):
                output[lang] = res
            else:
                output[lang] = text
        return output

    async def translate(self, text: str) -> str:
        return await self.translate_to_lang(text, settings.target_lang)

    async def process_partial_chunk(self, audio_chunk: np.ndarray, target_langs: list[str], sample_rate: int = 16000) -> dict:
        """Procesa un fragmento provisional de audio en curso para subtitulado palabra a palabra."""
        original_text = await self.transcribe(audio_chunk, sample_rate)
        if not original_text or len(original_text) < 2:
            return {"original": "", "translations": {}, "is_partial": True}

        # Si el texto parcial no ha cambiado respecto al slice anterior, reusar cache
        if original_text == self._last_partial_text:
            return {
                "original": original_text,
                "translations": self._last_partial_translations,
                "is_partial": True
            }

        self._last_partial_text = original_text
        translations = await self.translate_multi(original_text, target_langs)
        self._last_partial_translations = translations

        return {
            "original": original_text,
            "translations": translations,
            "is_partial": True
        }

    async def process_chunk_multi(self, audio_chunk: np.ndarray, target_langs: list[str], sample_rate: int = 16000) -> dict:
        """Procesa el chunk final consolidado."""
        self.reset_partial_cache()
        t0 = time.perf_counter()
        original_text = await self.transcribe(audio_chunk, sample_rate)
        if not original_text:
            return {"original": "", "translations": {}, "latency_ms": 0, "is_partial": False}

        translations = await self.translate_multi(original_text, target_langs)
        t1 = time.perf_counter()
        latency_ms = int((t1 - t0) * 1000)

        primary_translated = translations.get(settings.target_lang, next(iter(translations.values()), original_text))
        logger.info(f"[{latency_ms}ms FINAL] '{original_text}' -> {translations}")

        return {
            "original": original_text,
            "translations": translations,
            "translated": primary_translated,
            "latency_ms": latency_ms,
            "is_partial": False
        }
