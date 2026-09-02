# 📘 Manual de Integración con OBS Studio: AND Live Translator

Este manual explica cómo integrar **AND Live Translator** en producciones y streams en directo realizados con **OBS Studio** (v28, v29, v30 y superiores).

---

## 1. Añadir el Rótulo de Subtítulos (Browser Source)

1. En OBS Studio, en el panel de **Fuentes** (Sources), haz clic en el botón +.
2. Selecciona **Navegador** (Browser).
3. Nómbralo Subtítulos Live y pulsa **Aceptar**.
4. Configura los parámetros:
   - **URL:** http://127.0.0.1:17494/overlay
   - **Ancho (Width):** 1920
   - **Alto (Height):** 1080
   - **FPS:** 30 o 60
   - Marca: **Controlar audio vía OBS** (opcional)
   - Desmarca: **Desactivar cuando no sea visible** (para mantener el WebSocket siempre listo)
5. Pulsa **Aceptar**.
6. Coloca la fuente en la parte superior de tu lista de capas de la escena para que se dibuje por encima del video del invitado.

---

## 2. Ingesta del Audio del Ponente en OBS

1. Si el ponente entra por Discord, Zoom o navegador web, asigna la salida de audio de esa aplicación a un cable virtual (ej: VB-Audio Virtual Cable).
2. En el panel de control del traductor ([http://127.0.0.1:17494/](http://127.0.0.1:17494/)):
   - En **Entrada del Ponente**, selecciona el cable virtual de entrada.
   - En **Salida para vMix/OBS**, selecciona tu segundo cable virtual o el dispositivo de monitorización de OBS.

---

## 3. Mezcla y Ducking Nativo en OBS Studio (Sidechain)

Si prefieres que OBS Studio gestione la atenuación del volumen del ponente original:

1. En el **Mezclador de Audio** de OBS, haz clic en los tres puntos de la pista del ponente original y selecciona **Filtros**.
2. Añade un filtro de tipo **Compresor**.
3. En el desplegable **Fuente de atenuación (Sidechain / Ducking)**, selecciona la pista de audio traducido.
4. Ajustes recomendados:
   - **Relación:** 4:1
   - **Umbral:** -24 dB
   - **Ataque:** 20 ms
   - **Liberación:** 300 ms
5. Cada vez que el motor hable en español, OBS bajará automáticamente el volumen del ponente original.
