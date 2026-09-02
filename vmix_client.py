import logging
import urllib.parse
import httpx
import xml.etree.ElementTree as ET
from config import settings

logger = logging.getLogger("vmix_client")

class VMixClient:
    def __init__(self, host: str = None, port: int = None):
        self.host = host or settings.vmix_host
        self.port = port or settings.vmix_port
        self.base_url = f"http://{self.host}:{self.port}/api/"
        self._client = httpx.AsyncClient(timeout=2.0)

    async def is_online(self) -> bool:
        """Comprueba si vMix esta abierto y responde en el puerto de API."""
        try:
            res = await self._client.get(self.base_url)
            return res.status_code == 200
        except Exception:
            return False

    async def set_text(self, text: str, input_name: str = None, field_name: str = None) -> bool:
        """Actualiza el texto de un GT Title o Titulo estandar en vMix."""
        target_input = input_name or settings.vmix_title_input
        target_field = field_name or settings.vmix_title_field
        
        encoded_val = urllib.parse.quote(text)
        url = (
            f"{self.base_url}?Function=SetText"
            f"&Input={urllib.parse.quote(target_input)}"
            f"&SelectedName={urllib.parse.quote(target_field)}"
            f"&Value={encoded_val}"
        )
        try:
            res = await self._client.get(url)
            if res.status_code == 200:
                logger.info(f"[vMix] Subtitulo enviado a [{target_input}]: {text}")
                return True
            else:
                logger.warning(f"[vMix] Fallo SetText ({res.status_code}): {res.text}")
                return False
        except Exception as e:
            logger.warning(f"[vMix] No se pudo enviar subtitulo a vMix: {e}")
            return False

    async def clear_text(self, input_name: str = None, field_name: str = None) -> bool:
        """Limpia el rotulo de subtitulos."""
        return await self.set_text("", input_name, field_name)

    async def set_fader(self, input_name: str, volume_percent: int) -> bool:
        """Ajusta el fader de un input de vMix (0-100%)."""
        url = (
            f"{self.base_url}?Function=SetVolumePercent"
            f"&Input={urllib.parse.quote(input_name)}"
            f"&Value={volume_percent}"
        )
        try:
            res = await self._client.get(url)
            return res.status_code == 200
        except Exception as e:
            logger.warning(f"[vMix] Error SetVolumePercent: {e}")
            return False

    async def list_inputs(self) -> list[dict]:
        """Obtiene la lista de entradas activas de vMix analizando el XML de estado."""
        try:
            res = await self._client.get(self.base_url)
            if res.status_code != 200:
                return []
            
            root = ET.fromstring(res.text)
            inputs = []
            for inp in root.findall(".//input"):
                inputs.append({
                    "key": inp.get("key"),
                    "number": inp.get("number"),
                    "type": inp.get("type"),
                    "title": inp.get("title"),
                    "shortTitle": inp.get("shortTitle"),
                    "state": inp.get("state"),
                    "muted": inp.get("muted") == "True",
                    "volume": float(inp.get("volume", 0)),
                })
            return inputs
        except Exception as e:
            logger.warning(f"[vMix] No se pudo parsear XML de vMix: {e}")
            return []

    async def close(self):
        await self._client.aclose()
