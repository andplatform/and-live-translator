# 📕 Manual de Integración con vMix: AND Live Translator

Este manual describe paso a paso cómo integrar **AND Live Translator** en una realización profesional con **vMix** (versiones 24, 25, 26, 27 y superiores).

---

## 🗺️ Mapa General de Ruteo Broadcast

`
  [PONENTE REMOTO] 
  (vMix Call / Zoom)
         │
         ▼
  ┌──────────────┐          ┌──────────────────────┐          ┌──────────────┐
  │ vMix INPUT 1 │─────────►│  AUDIO BUS A (Floor) │─────────►│ TRANSLATOR   │
  └──────────────┘          └──────────────────────┘          │   ENGINE     │
                                                              └──────┬───────┘
                                                                     │
                 ┌───────────────────────────────────────────────────┼───────────────────────────┐
                 │ (Subtítulos en vivo)                              │ (Audio traducido)         │ (Mix con Ducking)
                 ▼                                                   ▼                           ▼
  ┌──────────────────────────────┐                    ┌───────────────────────────┐ ┌───────────────────────────┐
  │ RÓTULO GT TITLE / OVERLAY    │                    │ vMix INPUT 2: Doblaje     │ │ vMix INPUT 3: Ducking Mix │
  │ (API HTTP SetText o Browser) │                    │ (Asignado a Master)       │ │ (Asignado a Master)       │
  └──────────────────────────────┘                    └───────────────────────────┘ └───────────────────────────┘
`

---

## 1. Configuración de los Buses de Audio en vMix

Para poder gestionar de forma independiente el audio original del invitado y el audio traducido:

1. En vMix, ve a **Settings** (engranaje arriba a la derecha) ➔ **Audio Outputs**.
2. Habilita al menos:
   - **Master:** Salida principal del programa (hacia tu emisión / streaming).
   - **Bus A:** Asígnalo a tu dispositivo de loopback o cable virtual (ej: Line 1 (VB-Audio Virtual Cable) o CABLE Input).
   - **Bus B:** Salida auxiliar para monitorización o grabación limpia si se requiere.
3. Haz clic en **OK** para aplicar y reiniciar el motor de audio de vMix.

---

## 2. Ingesta del Audio del Ponente hacia el Traductor

1. En la entrada de vMix donde entra el ponente (por ejemplo, Input 1: vMix Call o NDI: Invitado):
   - Haz clic en el botón **Audio** de esa entrada en el mezclador.
   - Marca la casilla **A** (para enviar su voz al Bus A).
   - **Desmarca** la casilla **M** (Master) si no quieres que la voz original en inglés/otro idioma salga por la emisión principal.
2. Abre el panel del traductor en tu navegador: [http://127.0.0.1:17494/](http://127.0.0.1:17494/)
3. En el desplegable **Entrada del Ponente**, selecciona el cable virtual donde vMix está enviando el Bus A (ej: [15] CABLE Output (VB-Audio Point)).
4. Verás cómo el **Vúmetro en Vivo** del panel reacciona inmediatamente a la voz del ponente.

---

## 3. Rótulos y Subtítulos en Pantalla (Dos Métodos)

### Método A: Web Browser Input (Recomendado — Ultra-rápido y animado)
1. En vMix, haz clic abajo a la izquierda en **Add Input** ➔ **Web Browser**.
2. Configura los campos:
   - **URL:** http://127.0.0.1:17494/overlay
   - **Width:** 1920
   - **Height:** 1080
   - Marca la casilla **Enable Transparent Background** (Fondo transparente).
3. Haz clic en **OK**.
4. En la botonera de vMix de esa nueva entrada, haz clic en **1** o **2** (Overlay 1 u Overlay 2).
5. Ya tienes un rótulo inferior profesional con desenfoque de cristal (glassmorphism) que entra automáticamente cuando el ponente habla y se oculta en los silencios.

---

### Método B: Título Nativo de vMix (GT Title oficial vía API HTTP)
Si prefieres usar un rótulo gráfico diseñado por ti con vMix GT Title Designer:

1. En vMix, activa la API Web:
   - Ve a **Settings ➔ Web Controller**.
   - Marca **Enable** en el puerto 8088.
2. Añade tu GT Title a vMix (**Add Input ➔ Title**).
3. Renombra esa entrada a Subtitulos (o el nombre que prefieras).
4. En el panel de control del traductor ([http://127.0.0.1:17494/](http://127.0.0.1:17494/)):
   - En **Input Title vMix**, escribe: Subtitulos.
   - En **Campo de Texto**, escribe el nombre del bloque de texto (por defecto Headline.Text o Message.Text).
   - Haz clic en **Actualizar Destino**.
   - Haz clic en **🧪 Probar Rótulo**: verás aparecer el texto de prueba en tu rótulo de vMix al instante.

---

## 4. Audio Doblado y Mezcla con Ducking

Dispones de cuatro modos seleccionables al vuelo desde el panel web:

| Modo | Comportamiento en vMix | Recomendado para |
|---|---|---|
| **📺 Todo (Sub + Voz)** | Muestra el rótulo en pantalla y emite audio sintetizado en español. | Conexiones de alta relevancia informativa. |
| **🎙️ Mix con Ducking** | El audio original del ponente se atenúa automáticamente a -16dB y la voz traducida entra al frente a 0dB. | Estilo documental / informativos de televisión. |
| **🗣️ Solo Doblaje** | Pasa únicamente la traducción limpia; oculta la voz original por completo. | Conferencias y ponencias técnicas largas. |
| **💬 Solo Subtítulos** | Sin voz sintética; mantiene la voz original íntegra con rótulo inferior. | Entrevistas acústicas o cuando se desea oír el idioma original. |

---

## 5. Circuito de Retorno (IFB) para el Ponente por vMix Call

Cuando el ponente está en remoto por **vMix Call**, necesita escuchar las preguntas del presentador desde el plató sin escuchar su propia voz repetida con retardo (Mix-Minus):

1. En vMix, abre el engranaje de configuración del input de **vMix Call**.
2. Ve a la pestaña **Audio**:
   - En el desplegable **Audio Return to Caller**, cambia Master por **Bus C** o **Bus B**.
3. En el mezclador de audio de vMix:
   - Asigna el micrófono del presentador de plató al **Bus C**.
   - Asegúrate de que el input del ponente **NO** tenga marcado el **Bus C** (esto evita que el ponente se escuche a sí mismo con eco).
4. El ponente recibirá un retorno limpio y directo en su auricular.
