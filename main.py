import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings, SUPPORTED_LANGUAGES
from vmix_client import VMixClient
from stt_translator import STTTranslator
from tts_player import TTSAudioPlayer
from vad_chunker import VADAudioChunker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("live_translator")

@dataclass
class WSClient:
    ws: WebSocket
    lang: str = "es"
    dual: bool = False

class ConnectionManager:
    def __init__(self):
        self.clients: list[WSClient] = []

    async def connect(self, websocket: WebSocket, lang: str = "es", dual: bool = False):
        await websocket.accept()
        client = WSClient(ws=websocket, lang=lang, dual=dual)
        self.clients.append(client)
        return client

    def disconnect(self, websocket: WebSocket):
        self.clients = [c for c in self.clients if c.ws != websocket]

    async def broadcast(self, message: dict):
        for client in list(self.clients):
            try:
                await client.ws.send_json(message)
            except Exception:
                self.disconnect(client.ws)

    async def broadcast_translations(self, original: str, translations: dict[str, str], latency_ms: int):
        for client in list(self.clients):
            try:
                translated = translations.get(client.lang, translations.get(settings.target_lang, original))
                msg = {
                    "type": "translation",
                    "original": original,
                    "translated": translated,
                    "translations": translations,
                    "lang": client.lang,
                    "dual": client.dual,
                    "latency_ms": latency_ms
                }
                await client.ws.send_json(msg)
            except Exception:
                self.disconnect(client.ws)

ws_manager = ConnectionManager()

last_vu_time = 0
def on_vu_level(level: int):
    global last_vu_time
    loop = asyncio.get_event_loop()
    now = loop.time()
    if now - last_vu_time >= 0.08:
        last_vu_time = now
        asyncio.create_task(ws_manager.broadcast({"type": "vu", "level": level}))

vmix = VMixClient()
translator = STTTranslator()
tts_player = TTSAudioPlayer(output_device_name=settings.output_device)
chunker = VADAudioChunker(device_index=settings.input_device, vu_callback=on_vu_level)

background_task = None

async def audio_processing_loop():
    logger.info("Iniciando bucle de captura y procesamiento multi-idioma...")
    try:
        await chunker.start()
        async for chunk in chunker.speech_chunks():
            needed_langs = set(settings.active_target_languages)
            for c in ws_manager.clients:
                if c.lang:
                    needed_langs.add(c.lang)

            res = await translator.process_chunk_multi(chunk, list(needed_langs), sample_rate=chunker.sample_rate)
            original = res["original"]
            translations = res["translations"]
            latency_ms = res["latency_ms"]

            if not original or not translations:
                continue

            await ws_manager.broadcast_translations(original, translations, latency_ms)

            primary_text = translations.get(settings.target_lang, next(iter(translations.values()), original))
            if settings.operation_mode in ["all", "subtitles_only"] and settings.vmix_enabled:
                asyncio.create_task(vmix.set_text(primary_text))

            if settings.operation_mode in ["all", "voice_only", "voice_ducking"]:
                asyncio.create_task(
                    tts_player.play_voice_or_duck(
                        primary_text,
                        original_chunk=chunk,
                        orig_sample_rate=chunker.sample_rate
                    )
                )

    except asyncio.CancelledError:
        logger.info("Bucle de audio cancelado.")
    except Exception as e:
        logger.error(f"Error en bucle de audio: {e}", exc_info=True)
    finally:
        await chunker.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_task
    background_task = asyncio.create_task(audio_processing_loop())
    yield
    if background_task:
        background_task.cancel()
    await vmix.close()
    await tts_player.close()

app = FastAPI(title="AND Live Translator", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open(STATIC_DIR / "index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/overlay", response_class=HTMLResponse)
async def get_overlay():
    with open(STATIC_DIR / "overlay.html", "r", encoding="utf-8") as f:
        return f.read()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    lang = websocket.query_params.get("lang", settings.target_lang)
    dual = websocket.query_params.get("dual", "0") in ["1", "true", "yes"]
    await ws_manager.connect(websocket, lang=lang, dual=dual)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# --- APIs de Configuración en Tiempo Real y Persistencia ---

@app.get("/api/config")
async def get_config():
    return {
        **settings.model_dump(),
        "supported_languages": SUPPORTED_LANGUAGES
    }

@app.get("/api/audio-devices")
async def get_audio_devices():
    devices = VADAudioChunker.list_audio_devices()
    return {
        "inputs": devices["inputs"],
        "outputs": devices["outputs"],
        "current_input": settings.input_device,
        "current_output": settings.output_device
    }

class DeviceSelection(BaseModel):
    input_device: str | int | None = None
    output_device: str | int | None = None

@app.post("/api/audio-devices")
async def set_audio_devices(data: DeviceSelection):
    if data.input_device is not None:
        settings.input_device = data.input_device
        await chunker.switch_device(data.input_device)
        logger.info(f"Dispositivo de entrada cambiado a: {data.input_device}")

    if data.output_device is not None:
        settings.output_device = data.output_device
        tts_player.__init__(output_device_name=data.output_device)
        logger.info(f"Dispositivo de salida cambiado a: {data.output_device}")

    settings.save_persistent()
    return {"success": True, "input": settings.input_device, "output": settings.output_device}

class LanguageUpdate(BaseModel):
    source_lang: str
    target_lang: str = "es"

@app.post("/api/language")
async def update_language(data: LanguageUpdate):
    settings.source_lang = data.source_lang
    settings.target_lang = data.target_lang
    settings.save_persistent()
    logger.info(f"Idiomas actualizados: {settings.source_lang} -> {settings.target_lang}")
    return {"success": True, "source": settings.source_lang, "target": settings.target_lang}

class ActiveLanguagesUpdate(BaseModel):
    languages: list[str]

@app.post("/api/active-languages")
async def update_active_languages(data: ActiveLanguagesUpdate):
    settings.active_target_languages = data.languages
    settings.save_persistent()
    logger.info(f"Idiomas concurrentes activos: {settings.active_target_languages}")
    return {"success": True, "active_languages": settings.active_target_languages}

@app.get("/api/vmix-status")
async def get_vmix_status():
    online = await vmix.is_online()
    return {"online": online, "host": settings.vmix_host, "port": settings.vmix_port}

@app.get("/api/vmix-inputs")
async def get_vmix_inputs():
    inputs = await vmix.list_inputs()
    return {"inputs": inputs}

class GlossaryUpdate(BaseModel):
    glossary: list[str]

@app.post("/api/glossary")
async def update_glossary(data: GlossaryUpdate):
    settings.glossary = data.glossary
    settings.save_persistent()
    logger.info(f"Glosario actualizado: {settings.glossary}")
    return {"success": True, "glossary": settings.glossary}

class ModeUpdate(BaseModel):
    mode: str

@app.post("/api/mode")
async def update_mode(data: ModeUpdate):
    if data.mode in ["all", "voice_ducking", "voice_only", "subtitles_only"]:
        settings.operation_mode = data.mode
        settings.save_persistent()
        logger.info(f"Modo de operacion cambiado a: {settings.operation_mode}")
        return {"success": True, "mode": settings.operation_mode}
    return JSONResponse(status_code=400, content={"error": "Modo invalido"})

class VmixConfigUpdate(BaseModel):
    vmix_title_input: str
    vmix_title_field: str

@app.post("/api/vmix-config")
async def update_vmix_config(data: VmixConfigUpdate):
    settings.vmix_title_input = data.vmix_title_input
    settings.vmix_title_field = data.vmix_title_field
    settings.save_persistent()
    return {"success": True, "input": settings.vmix_title_input, "field": settings.vmix_title_field}

class DryTestPhrase(BaseModel):
    text: str

@app.post("/api/test-phrase")
async def test_phrase(data: DryTestPhrase):
    needed_langs = list(set(settings.active_target_languages + [settings.target_lang]))
    translations = await translator.translate_multi(data.text, needed_langs)
    
    await ws_manager.broadcast_translations(data.text, translations, latency_ms=140)

    primary = translations.get(settings.target_lang, data.text)
    if settings.vmix_enabled:
        await vmix.set_text(primary)

    return {"original": data.text, "translations": translations, "primary": primary}

class VoiceTestRequest(BaseModel):
    text: str = "Prueba de doblaje en directo. El sistema de audio está funcionando correctamente."

@app.post("/api/test-voice")
async def test_voice(data: VoiceTestRequest):
    try:
        await tts_player.play_voice_or_duck(data.text)
        return {"success": True}
    except Exception as e:
        logger.error(f"Error reproduciendo voz de prueba: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.server_port, reload=False)
