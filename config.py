import os
import json
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Cargar .env.local de la raiz o .env local del servicio
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
env_local_path = ROOT_DIR / ".env.local"
service_env = Path(__file__).resolve().parent / ".env"
PERSISTENT_CONFIG_FILE = Path(__file__).resolve().parent / "config.json"

if service_env.exists():
    load_dotenv(dotenv_path=service_env, override=False)
elif env_local_path.exists():
    load_dotenv(dotenv_path=env_local_path, override=False)
else:
    load_dotenv()

SUPPORTED_LANGUAGES = {
    "auto": "Detección Automática",
    "en": "Inglés (English)",
    "es": "Español",
    "fr": "Francés (Français)",
    "de": "Alemán (Deutsch)",
    "it": "Italiano",
    "pt": "Portugués (Português)",
    "zh": "Chino (Mandarin)",
    "ja": "Japonés (Japanese)",
    "ru": "Ruso (Russian)",
    "ar": "Árabe (Arabic)",
    "nl": "Holandés (Nederlands)"
}

class TranslatorSettings(BaseModel):
    # vMix HTTP API
    vmix_host: str = Field(default=os.getenv("VMIX_HOST", "127.0.0.1"))
    vmix_port: int = Field(default=int(os.getenv("VMIX_PORT", "8088")))
    vmix_title_input: str = Field(default=os.getenv("VMIX_TITLE_INPUT", "Subtitulos"))
    vmix_title_field: str = Field(default=os.getenv("VMIX_TITLE_FIELD", "Headline.Text"))
    vmix_enabled: bool = Field(default=True)

    # Audio Routing
    input_device: str | int | None = Field(default=os.getenv("AUDIO_INPUT_DEVICE", None))
    output_device: str | int | None = Field(default=os.getenv("AUDIO_OUTPUT_DEVICE", None))
    sample_rate: int = 16000
    channels: int = 1

    # Languages
    source_lang: str = Field(default=os.getenv("TRANSLATOR_SOURCE_LANG", "en"))
    target_lang: str = Field(default=os.getenv("TRANSLATOR_TARGET_LANG", "es"))
    active_target_languages: list[str] = Field(default=["es", "en", "fr", "de"])

    # Glossary / Contextual Prompt to eliminate hallucinations
    glossary: list[str] = Field(default=[
        "vMix", "NDI", "Jackie", "Manu Gordillo", "Almeria", 
        "Center Brain", "Sentinel", "OBS", "Live Stream"
    ])
    
    # Operation Mode: 'subtitles_only', 'voice_only', 'voice_ducking', 'all'
    operation_mode: str = Field(default="all")
    ducking_background_volume: float = 0.15 # -16dB para el audio original

    # API Keys & Services
    groq_api_key: str = Field(default=os.getenv("GROQ_API_KEY", ""))
    openai_api_key: str = Field(default=os.getenv("OPENAI_API_KEY", ""))
    voicebox_url: str = Field(default=os.getenv("VOICEBOX_URL", "http://127.0.0.1:17493"))
    voicebox_profile_id: str = Field(default=os.getenv("VOICEBOX_PROFILE_ID", ""))
    
    # Web UI / Overlay Server Port
    server_port: int = 17494

    def save_persistent(self):
        """Guarda la configuración persistente en config.json (sin almacenar claves de API en claro)."""
        data = {
            "vmix_host": self.vmix_host,
            "vmix_port": self.vmix_port,
            "vmix_title_input": self.vmix_title_input,
            "vmix_title_field": self.vmix_title_field,
            "input_device": self.input_device,
            "output_device": self.output_device,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "active_target_languages": self.active_target_languages,
            "glossary": self.glossary,
            "operation_mode": self.operation_mode
        }
        try:
            with open(PERSISTENT_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            pass

def load_settings() -> TranslatorSettings:
    s = TranslatorSettings()
    if PERSISTENT_CONFIG_FILE.exists():
        try:
            with open(PERSISTENT_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for k, v in saved.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
        except Exception:
            pass
    return s

settings = load_settings()
