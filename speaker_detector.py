"""
SpeakerDetector — diarización ligera basada en huella espectral.

Sin dependencias externas más allá de numpy/scipy (ya presentes).
Funciona extrayendo un perfil espectral promedio de cada chunk de audio
y comparando la similitud coseno con los perfiles de hablantes conocidos.

Precisión: alta para voces claramente distintas (hombre/mujer, acentos
distintos). Moderada para hablantes del mismo sexo con voces similares.
Latencia: ~5–15ms por chunk en CPU.
"""
import numpy as np
from scipy.signal import get_window
from scipy.fft import rfft


# Número máximo de hablantes a rastrear simultáneamente
MAX_SPEAKERS = 4

# Umbral de similitud coseno: por encima → mismo hablante, por debajo → nuevo
# 0.82 es un buen punto de partida; bajar si detecta demasiados cambios falsos
SIMILARITY_THRESHOLD = 0.82

# Peso de la media móvil al actualizar el perfil de un hablante conocido
# 0.3 → el perfil se adapta suavemente a cambios de entonación
ADAPTATION_ALPHA = 0.30

# Colores CSS asignados a cada hablante (max 4)
SPEAKER_COLORS = [
    "#38bdf8",   # Sky-blue  — Hablante A
    "#fbbf24",   # Amber     — Hablante B
    "#4ade80",   # Green     — Hablante C
    "#f472b6",   # Pink      — Hablante D
]


class SpeakerDetector:
    """
    Detecta cambios de hablante comparando huellas espectrales entre chunks.

    Uso:
        detector = SpeakerDetector()
        speaker_id, color = detector.identify(audio_chunk, sample_rate=16000)
    """

    def __init__(
        self,
        max_speakers: int = MAX_SPEAKERS,
        threshold: float = SIMILARITY_THRESHOLD,
    ):
        self.max_speakers = max_speakers
        self.threshold = threshold

        # Diccionario: speaker_id → embedding (np.ndarray normalizado)
        self._profiles: dict[int, np.ndarray] = {}

        # Último hablante identificado
        self.last_speaker_id: int = 0

    # ── Extracción de huella espectral ────────────────────────────────────────

    def _extract_embedding(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Perfil espectral medio de corta duración.
        Usa ventanas de Hann de 25 ms con solapamiento de 10 ms.
        Devuelve vector normalizado (coseno-listo).
        """
        frame_len = int(sr * 0.025)   # 25 ms
        hop_len   = int(sr * 0.010)   # 10 ms paso
        win       = get_window("hann", frame_len, fftbins=False)

        spectra = []
        for start in range(0, len(audio) - frame_len, hop_len):
            frame    = audio[start : start + frame_len] * win
            spectrum = np.abs(rfft(frame))
            spectra.append(spectrum)

        if not spectra:
            # Chunk demasiado corto — devolver vector nulo
            return np.zeros(frame_len // 2 + 1)

        mean_spec = np.mean(spectra, axis=0)

        # Normalización L2 para similitud coseno sin escala de amplitud
        norm = np.linalg.norm(mean_spec)
        if norm > 1e-8:
            mean_spec = mean_spec / norm

        return mean_spec

    @staticmethod
    def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        """Similitud coseno entre dos vectores normalizados."""
        # Con normalización L2 previa el dot product = coseno directamente
        return float(np.clip(np.dot(a, b), -1.0, 1.0))

    # ── Identificación principal ───────────────────────────────────────────────

    def identify(self, audio: np.ndarray, sr: int = 16000) -> tuple[int, str]:
        """
        Identifica el hablante del chunk de audio.

        Devuelve:
            (speaker_id: int, color: str)   — color CSS listo para el overlay
        """
        embedding = self._extract_embedding(audio, sr)

        # ── Primer chunk: registrar como Hablante 0 ────────────────────────
        if not self._profiles:
            self._profiles[0] = embedding
            self.last_speaker_id = 0
            return 0, SPEAKER_COLORS[0]

        # ── Buscar el hablante más parecido ────────────────────────────────
        best_id  : int   = -1
        best_sim : float = -1.0

        for spk_id, profile in self._profiles.items():
            sim = self._cosine_sim(embedding, profile)
            if sim > best_sim:
                best_sim = sim
                best_id  = spk_id

        if best_sim >= self.threshold:
            # ── Hablante conocido: actualizar perfil con media móvil ────────
            a = ADAPTATION_ALPHA
            self._profiles[best_id] = a * embedding + (1 - a) * self._profiles[best_id]
            # Renormalizar tras la mezcla
            n = np.linalg.norm(self._profiles[best_id])
            if n > 1e-8:
                self._profiles[best_id] /= n

            self.last_speaker_id = best_id
            color = SPEAKER_COLORS[best_id % len(SPEAKER_COLORS)]
            return best_id, color

        else:
            # ── Nuevo hablante detectado ───────────────────────────────────
            if len(self._profiles) < self.max_speakers:
                new_id = max(self._profiles.keys()) + 1
                self._profiles[new_id] = embedding
                self.last_speaker_id = new_id
                color = SPEAKER_COLORS[new_id % len(SPEAKER_COLORS)]
                return new_id, color
            else:
                # Ya tenemos el máximo de hablantes → asignar al más similar
                self._profiles[best_id] = (
                    ADAPTATION_ALPHA * embedding + (1 - ADAPTATION_ALPHA) * self._profiles[best_id]
                )
                n = np.linalg.norm(self._profiles[best_id])
                if n > 1e-8:
                    self._profiles[best_id] /= n
                self.last_speaker_id = best_id
                color = SPEAKER_COLORS[best_id % len(SPEAKER_COLORS)]
                return best_id, color

    def reset(self):
        """Reinicia todos los perfiles (útil al cambiar de escena o fuente de audio)."""
        self._profiles.clear()
        self.last_speaker_id = 0
