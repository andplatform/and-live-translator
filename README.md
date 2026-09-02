# 🎙️ AND Live Translator (vMix Broadcast Edition)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![vMix Compatible](https://img.shields.io/badge/vMix-24%20--%2027+-red.svg)](https://www.vmix.com/)
[![OBS Studio](https://img.shields.io/badge/OBS%20Studio-Compatible-purple.svg)](https://obsproject.com/)
[![Latency](https://img.shields.io/badge/Latency-%3C150ms-brightgreen.svg)]()

> **Motor profesional de traducción en tiempo real, subtitulado dinámico y doblaje simultáneo (Speech-to-Speech) para realización en directo con vMix y OBS Studio.**

---

## 📺 El Problema en Realización en Directo

En programas de televisión, directos y eventos con ponentes internacionales que entran por llamada remota (vMix Call, Zoom, Teams, NDI o SDI), los traductores estándar fallan estrepitosamente:
1. **Alucinaciones y bucles:** En los silencios, carraspeos o fondos musicales, los modelos STT inventan palabras que nadie ha dicho.
2. **Deformación de términos:** No respetan nombres propios, marcas o terminología técnica del programa.
3. **Latencias inaceptables:** Tiempos de respuesta de 4 a 10 segundos que rompen el ritmo televisivo.
4. **Cero integración broadcast:** No ofrecen rótulos en vivo por API, ni ruteo de buses de audio, ni retorno IFB para el orador.

**AND Live Translator** resuelve la cadena completa de producción en directo con latencias inferiores a **150 ms** en transcripción y traducción.

---

## ⚡ Características Principales

- **Filtro VAD Acústico Anti-Alucinaciones:** Segmenta la voz mediante detección de energía y pausas naturales de respiración (300–400ms). Cero alucinaciones en silencios.
- **Glosario Contextual en Vivo:** Inyecta palabras clave, marcas y nombres propios en el reconocedor. Se puede editar en caliente desde el panel sin reiniciar.
- **Cuatro Modos de Salida en Directo:**
  - 📺 **Todo (Sub + Voz):** Rótulo en pantalla y audio doblado simultáneo.
  - 🎙️ **Mix con Ducking:** Efecto documental automático (original atenuado a -16dB + traducción al frente a 0dB).
  - 🗣️ **Solo Doblaje:** Pasa únicamente la traducción sintetizada.
  - 💬 **Solo Subtítulos:** Sin doblaje de audio; conserva la voz original con subtítulos inferiores.
- **Doble Salida de Subtítulos para vMix:**
  - **Web Browser Input:** Overlay transparente fluido en http://127.0.0.1:17494/overlay.
  - **vMix HTTP API:** Envío directo mediante Function=SetText a cualquier GT Title o XAML oficial de vMix.
- **Ruteo de Audio en Caliente:** Selector desplegable de micrófonos, tarjetas de sonido y cables virtuales (VB-Audio, Virtual Cable, WASAPI) desde el navegador.
- **Soporte Multi-Idioma:** Entrada en inglés, francés, alemán, italiano, portugués, chino, japonés, ruso o árabe, con salida directa en español televisivo.
- **Retorno IFB para el Ponente:** Circuito preparado para enviar al orador remoto el audio de programa limpio (Mix-Minus) o la traducción inversa.

---

## 🏗️ Arquitectura del Sistema

`
 [Entrada Ponente] ─────────────────────────────────────────────────────────────┐
 (vMix Call / NDI / Zoom)                                                       │
        │                                                                        │
        ▼ vMix Audio Bus A (Original / Floor)                                    │
 ┌──────────────────────────────────────────────────────────────┐                │
 │               AND LIVE TRANSLATOR DAEMON                     │                │
 │                                                              │                │
 │ 1. Ingesta: sounddevice / VB-Cable (48kHz Float32)           │                │
 │ 2. Silero / Energy VAD: Aislamiento por respiración (<30ms)   │                │
 │ 3. STT: Whisper Large v3 Turbo con Glosario Contextual       │                │
 │ 4. Traductor: Modelo broadcast en streaming (<120ms)         │                │
 │ 5. Dispatcher de Salidas Simultáneas:                        │                │
 └──────┬──────────────────────┬──────────────────────┬─────────┘                │
        │                      │                      │                          │
        ▼                      ▼                      ▼                          │
 [Rótulo Subtítulo]     [Audio Doblado]        [Mix con Ducking]                 │
 Envío HTTP SetText     Audio sintético por    Original (-16dB) +                │
 y WebSocket Overlay    Virtual Cable B hacia  Doblaje (0dB) para                │
 (vMix Browser Input)   vMix Audio Bus B       emisión directa                   │
        │                      │                      │                          │
        └──────────────────────┼──────────────────────┘                          │
                               ▼                                                 │
                 [Mesa de Mezclas vMix (PGM)]                                    │
                 Control instantáneo por faders:                                 │
                 - Fader 1: Original Ponente (Bus A)                             │
                 - Fader 2: Doblaje (Bus B)                                      │
                 - Overlay: Rótulo ON / OFF                                      │
                                                                                 │
 ┌───────────────────────────────────────────────────────────────────────────────┘
 │ RETORNO AL PONENTE (IFB / Intercom / vMix Call):
 └─► Retorno limpio Mix-Minus o traducción inversa hacia el auricular del invitado.
`

---

## 🚀 Inicio Rápido en Windows (3 Pasos)

### 1. Clonar el Repositorio
`ash
git clone https://github.com/END-CENTER/and-live-translator.git
cd and-live-translator
`

### 2. Instalación Automática
Haz doble clic en:
`at
install.bat
`
*(O ejecuta install.ps1 en PowerShell. Creará el entorno virtual e instalará todas las dependencias necesarias).*

### 3. Configurar tu Clave de Groq
Abre el archivo generado .env con el Bloc de notas y pega tu clave API gratuita de Groq:
`env
GROQ_API_KEY=gsk_tu_clave_aqui
`
*(Puedes obtener una clave gratuita en 30 segundos en [https://console.groq.com/keys](https://console.groq.com/keys)).*

### 4. Arrancar
Haz doble clic en:
`at
start.bat
`
- **Panel de Control:** Abre [http://127.0.0.1:17494/](http://127.0.0.1:17494/)
- **Overlay de Subtítulos:** [http://127.0.0.1:17494/overlay](http://127.0.0.1:17494/overlay)

---

## 📖 Manuales de Integración Detallados

- 📕 **[Manual de Integración con vMix (MANUAL_VMIX.md)](MANUAL_VMIX.md)** — Configuración paso a paso de buses de audio, GT Titles, Web Browser Overlay, Ducking y retorno IFB por vMix Call.
- 📘 **[Manual de Integración con OBS Studio (MANUAL_OBS.md)](MANUAL_OBS.md)** — Configuración de fuentes de navegador y monitorización de audio.

---

## 🧪 Batería de Pruebas y Auditoría

El proyecto incluye una suite automatizada de pruebas end-to-end:

`ash
.venv\Scripts\python.exe tests/test_audit.py
`

Comprueba:
- ✅ Segmentación acústica y corte por VAD en silencios.
- ✅ Transcripción STT y preservación exacta de nombres técnicos con glosario.
- ✅ Conector HTTP de vMix (SetText y SetVolumePercent).
- ✅ Servidor WebSocket y entrega de paquetes al overlay.
- ✅ Medición de latencias reales.

---

## 📄 Licencia

Distribuido bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
