import os
import sys
import time
import asyncio
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

import numpy as np
from vad_chunker import VADAudioChunker
from stt_translator import STTTranslator

print("=" * 78)
print("  TEST UNITARIO: STREAMING PARTIALS (SUBTÍTULOS PALABRA A PALABRA)")
print("=" * 78)

async def test_chunker_partials():
    print("\n[*] Prueba 1: Emisión incremental de snapshots en VADAudioChunker...")
    chunker = VADAudioChunker(
        sample_rate=16000,
        frame_duration_ms=30,
        silence_threshold_db=-42.0,
        min_silence_duration_ms=300,
        min_speech_duration_ms=400,
        partial_interval_ms=250 # Rápido para el test
    )
    chunker._loop = asyncio.get_running_loop()
    chunker._is_running = True

    # Generar 1.5s de habla (tono 440Hz)
    sr = 16000
    frame_len = int(sr * 0.03) # 480 muestras
    t = np.linspace(0, 0.03, frame_len, endpoint=False)
    voice_frame = (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    silence_frame = np.zeros(frame_len, dtype=np.float32)

    # Inyectar 40 frames de voz (~1200ms)
    for _ in range(40):
        await chunker._queue.put(voice_frame)

    # Inyectar 15 frames de silencio (~450ms) para forzar corte final
    for _ in range(15):
        await chunker._queue.put(silence_frame)

    partials_received = 0
    finals_received = 0

    async def consume():
        nonlocal partials_received, finals_received
        async for chunk, is_final in chunker.speech_events():
            if not is_final:
                partials_received += 1
                print(f"  -> Snapshot parcial recibido: {len(chunk)} muestras ({len(chunk)/sr:.2f}s)")
            else:
                finals_received += 1
                print(f"  -> CHUNK FINAL recibido: {len(chunk)} muestras ({len(chunk)/sr:.2f}s)")
                break

    try:
        await asyncio.wait_for(consume(), timeout=2.5)
    except asyncio.TimeoutError:
        pass

    assert partials_received >= 2, f"Se esperaban al menos 2 partials, se recibieron {partials_received}"
    assert finals_received == 1, f"Se esperaba 1 final, se recibieron {finals_received}"
    print(f"  [OK] VAD emitió {partials_received} snapshots parciales y {finals_received} final.")

async def test_translator_partial():
    print("\n[*] Prueba 2: Traductor STT procesando fragmento parcial...")
    tr = STTTranslator()
    
    # Probar caché de partials
    tr.reset_partial_cache()
    # Mock / llamada con texto corto
    res = await tr.translate_to_lang("Welcome to the live show", "es")
    print(f"  -> Traducción parcial a español: '{res}'")
    assert len(res) > 0, "Traducción vacía"
    print("  [OK] Traductor procesó fragmento correctamente.")

async def main():
    await test_chunker_partials()
    await test_translator_partial()
    print("\n" + "=" * 78)
    print("  TODAS LAS PRUEBAS DE STREAMING PARTIALS PASARON CON ÉXITO")
    print("=" * 78 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
