import io
import re
import time
import logging
import asyncio
import numpy as np
import scipy.io.wavfile as wavfile
from collections import deque
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

# Ventana deslizante de contexto: almacena las últimas N frases traducidas
# para dar coherencia a pronombres, verbos e idiomas coloquiales
CONTEXT_WINDOW_SIZE = 4

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

    # 4. Normalizar espacios tipográficos no separables
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
        
        # Ventana de contexto deslizante por idioma destino
        # Almacena tuplas (texto_original, texto_traducido) de las últimas N frases
        self._context_buffers: dict[str, deque] = {}
        
        if settings.groq_api_key:
            try:
                from groq import AsyncGroq
                self.groq_client = AsyncGroq(api_key=settings.groq_api_key)
                logger.info("Cliente Groq activado para STT y Traducción ultra-rápida.")
            except Exception as e:
                logger.warning(f"No se pudo inicializar Groq: {e}")

    def _get_context_buffer(self, lang: str) -> deque:
        """Obtiene o crea el buffer de contexto para un idioma."""
        if lang not in self._context_buffers:
            self._context_buffers[lang] = deque(maxlen=CONTEXT_WINDOW_SIZE)
        return self._context_buffers[lang]

    def _push_context(self, lang: str, original: str, translated: str):
        """Añade una frase al historial de contexto del idioma."""
        buf = self._get_context_buffer(lang)
        buf.append((original, translated))

    def clear_context(self, lang: str = None):
        """Limpia el contexto de un idioma o de todos."""
        if lang:
            self._context_buffers.pop(lang, None)
        else:
            self._context_buffers.clear()

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
        
        # Whisper prompt: solo lista limpia de nombres propios para corregir ortografía sin alucinar
        whisper_prompt = ", ".join(settings.glossary) if settings.glossary else None
        source_lang = None if settings.source_lang in ["auto", "", None] else settings.source_lang

        if self.groq_client:
            try:
                transcription = await self.groq_client.audio.transcriptions.create(
                    file=("audio.wav", wav_bytes, "audio/wav"),
                    model="whisper-large-v3-turbo",
                    prompt=whisper_prompt,
                    language=source_lang,
                    response_format="text",
                    temperature=0.0,
                )
                res_str = str(transcription).strip()
                # Filtrar transcripciones fantasma de ruidos breves (ej: '.', ' ', 'you')
                if len(res_str) <= 1 or res_str.lower() in [".", "..", "...", "subtítulos", "gracias por ver"]:
                    return ""
                return res_str
            except Exception as e:
                logger.error(f"[STT Groq Error]: {e}")

        return ""

    async def translate_to_lang(self, text: str, target_lang: str) -> str:
        if not text or len(text.strip()) == 0:
            return ""

        if settings.source_lang == target_lang:
            return text

        lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)
        
        # ── Sistema de prompts mejorado ──────────────────────────────────────────
        # Instrucciones específicas para traducción natural y coloquial,
        # no traducción literal. Adaptación de modismos y expresiones.
        system_prompt = (
            f"Eres un intérprete simultáneo profesional de televisión en directo. "
            f"Tu tarea es traducir al {lang_name} de forma completamente natural, "
            f"como lo haría un hablante nativo en una conversación oral. "
            f"Reglas estrictas:\n"
            f"1. NUNCA traduzcas palabra por palabra. Usa el equivalente natural en {lang_name}.\n"
            f"2. Adapta los modismos, phrasal verbs e idioms a su equivalente coloquial.\n"
            f"3. Si la frase está incompleta (cortada a mitad), tradúcela tal cual sin completarla.\n"
            f"4. Mantén el registro informal/conversacional cuando el original lo sea.\n"
            f"5. Devuelve ÚNICA y EXCLUSIVAMENTE la traducción en una sola línea. "
            f"Sin comillas, sin explicaciones, sin prefijos."
        )

        # ── Construir mensajes con ventana de contexto deslizante ───────────────
        # Las últimas N frases como historial de conversación dan al modelo
        # contexto para resolver pronombres, verbos e idiomas correctamente
        messages = [{"role": "system", "content": system_prompt}]
        
        context_buf = self._get_context_buffer(target_lang)
        for (prev_original, prev_translated) in context_buf:
            messages.append({"role": "user", "content": prev_original})
            messages.append({"role": "assistant", "content": prev_translated})
        
        # Frase actual a traducir
        messages.append({"role": "user", "content": text})

        if self.groq_client:
            # 1. Intentar con qwen/qwen3.8-27b con ventana de contexto completa
            try:
                response = await self.groq_client.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=messages,
                    temperature=0.1,   # Ligera varianza para naturalidad, sin aleatoriedad excesiva
                    max_tokens=150,    # Aumentado para frases largas
                )
                raw = response.choices[0].message.content
                if raw:
                    result = clean_translation_text(raw)
                    if result:
                        # Guardar en contexto para la próxima frase
                        self._push_context(target_lang, text, result)
                        return result
            except Exception as e:
                logger.warning(f"[Translation Groq Qwen Fallback {target_lang}]: {e}")

            # 2. Respaldo con allam-2-7b — también pasa el contexto deslizante
            try:
                response = await self.groq_client.chat.completions.create(
                    model="allam-2-7b",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=150,
                )
                raw = response.choices[0].message.content
                if raw:
                    result = clean_translation_text(raw)
                    if result:
                        self._push_context(target_lang, text, result)
                        return result
            except Exception as e2:
                logger.warning(f"[Translation Groq Allam Fallback {target_lang}]: {e2}")

        return text


    async def translate_multi(self, text: str, target_langs: list[str]) -> dict[str, str]:
        """Traduce concurrentemente la misma frase a los idiomas solicitados."""
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

    async def process_chunk_multi(self, audio_chunk: np.ndarray, target_langs: list[str], sample_rate: int = 16000) -> dict:
        """Procesa una frase completa recortada por respiración o 2.5s máximo."""
        t0 = time.perf_counter()
        original_text = await self.transcribe(audio_chunk, sample_rate)
        if not original_text:
            return {"original": "", "translations": {}, "latency_ms": 0}

        translations = await self.translate_multi(original_text, target_langs)
        t1 = time.perf_counter()
        latency_ms = int((t1 - t0) * 1000)

        primary_translated = translations.get(settings.target_lang, next(iter(translations.values()), original_text))
        logger.info(f"[{latency_ms}ms] '{original_text}' -> {translations}")

        return {
            "original": original_text,
            "translations": translations,
            "translated": primary_translated,
            "latency_ms": latency_ms
        }
