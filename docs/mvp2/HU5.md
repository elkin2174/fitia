# MVP 2 — HU 5: Cambiar la velocidad de reproducción

Documentación técnica de la implementación frontend de la Historia de Usuario 5 del MVP 2 de FITIA: selector de velocidad de reproducción (0,75×, 1×, 1,25×), modulación del audio sin alteración de tono (*pitch preservation*), persistencia en almacenamiento local y tolerancia a fallos en `localStorage`.

> **Estado:** Implementado y probado. 123 pruebas frontend pasando en suite completa (24 nuevas dedicadas a HU3, HU4 y HU5). Cero llamadas a servicios de audio reales en pruebas automatizadas.

---

## 1. Propósito y Alcance

Permite a los estudiantes adaptar la cadencia de la explicación hablada según su nivel de familiaridad con la técnica: más lenta para principiantes analizando detalles posturales (0,75×), normal por defecto (1×) o más rápida para repasos ágiles (1,25×).

### Criterios de Aceptación
- **AC-5-1:** El usuario puede seleccionar entre las velocidades `0,75×`, `1×` o `1,25×`. El cambio se aplica en caliente sobre el audio en curso sin reiniciar ni cortar la reproducción, preservando el tono natural de la voz (`preservesPitch = true`).
- **AC-5-2:** La velocidad elegida se guarda en `localStorage` bajo la clave `fitia_playback_rate` y se aplica automáticamente a futuras sesiones o reaperturas; por defecto es `1×`.
- **AC-5-3:** Si `localStorage` no está disponible o lanza error (modo incógnito estricto, cuota excedida o directivas de seguridad), la aplicación utiliza `1×` silenciosamente sin interrumpir el funcionamiento ni mostrar errores al usuario.

---

## 2. Arquitectura y Componentes Frontend

Se implementó en `apps/web/src/features/voice/playbackRate.ts` y se integró en `PlaybackControls.tsx` y `AudioPlayer.ts`:

```text
apps/web/src/
└── features/
    └── voice/
        ├── playbackRate.ts         # Tipos PlaybackRate (0.75 | 1 | 1.25), loadPlaybackRate y savePlaybackRate
        ├── PlaybackControls.tsx    # Grupo de botones de velocidad con estado activo aria-pressed
        └── AudioPlayer.ts          # Aplicación a audio.playbackRate y audio.preservesPitch
```

### Gestión de Velocidad y Preservación de Tono
- **Configuración en Vivo:**
  Cuando el usuario presiona un botón de velocidad, se invoca `audioPlayer.setRate(rate)`.
  El reproductor actualiza la propiedad nativa `audio.playbackRate = rate` y asegura `audio.preservesPitch = true` (para evitar distorsión de voz ardilla o grave), manteniendo la posición de reproducción actual (`currentTime`).
- **Persistencia Segura en Almacenamiento Local:**
  - `loadPlaybackRate()`: Consulta `localStorage.getItem("fitia_playback_rate")`. Si no existe o no es uno de los valores válidos (`0.75`, `1`, `1.25`), devuelve `1` de manera segura dentro de un bloque `try / catch`.
  - `savePlaybackRate(rate)`: Almacena la cadena correspondiente. Cualquier excepción de `localStorage` es capturada y descartada silenciosamente.
- **Accesibilidad del Selector:**
  - Envuelto en un contenedor con `role="group"` y `aria-label="Velocidad de reproducción"`.
  - Cada opción es un elemento `<button type="button">` con atributo `aria-pressed={isSelected}` y `aria-label="Velocidad X"`.
  - La opción activa se resalta con el fondo primario (`bg-primary text-on-primary`), mientras que las demás muestran borde sobrio (`border-line bg-surface text-ink`).

---

## 3. Trazabilidad: Criterios de Aceptación vs Pruebas

| Criterio de Aceptación | Descripción | Pruebas Automatizadas |
|---|---|---|
| **AC-5-1** | Velocidades 0,75×, 1× y 1,25× se aplican en caliente sin reiniciar `currentTime` y con `preservesPitch = true`. | `apps/web/src/test/flows/voice.test.tsx::AC-5-1 a AC-5-3: velocidad 0,75×, 1×, 1,25×, persistencia y resiliencia en localStorage`<br>`apps/web/src/features/voice/AudioPlayer.test.ts::AC-5-1` |
| **AC-5-2** | La elección se persiste en `localStorage` y se recupera como velocidad inicial; por defecto 1×. | `apps/web/src/test/flows/voice.test.tsx::AC-5-1 a AC-5-3: velocidad 0,75×, 1×, 1,25×, persistencia y resiliencia en localStorage`<br>`apps/web/src/features/voice/playbackRate.test.ts::savePlaybackRate y loadPlaybackRate` |
| **AC-5-3** | Si `localStorage` falla o lanza excepción (modo incógnito, `SecurityError`), se usa 1× sin error. | `apps/web/src/features/voice/playbackRate.test.ts::si localStorage falla o lanza excepción, se usa 1× sin error` |

---

## 4. Guía de Prueba Manual (Dispositivo Móvil / Celular Real)

### Requisitos Previos
1. Acceder a FITIA desde un navegador móvil (Chrome, Safari, Firefox).
2. Abrir la hoja inferior de un ejercicio desde la pantalla `/hoy`.

### Pasos de Verificación
1. **Velocidad Inicial por Defecto (1×):**
   - Al abrir el ejercicio, verifica que el botón **1×** esté resaltado en color rojo primario con texto blanco (`aria-pressed="true"`), mientras que 0,75× y 1,25× aparecen con fondo claro y borde gris.
2. **Cambio en Caliente (AC-5-1):**
   - Pulsa «Escuchar».
   - Mientras la voz explica un paso, toca el botón **1,25×**.
   - Verifica que el audio aumenta su cadencia de inmediato sin pausas, sin chasquidos y sin empezar de nuevo la explicación. La voz debe sonar más rápida pero con su tono normal (no agudo).
   - Toca el botón **0,75×**. La voz debe reducir su velocidad de forma fluida, manteniendo la inteligibilidad.
3. **Persistencia entre Aperturas (AC-5-2):**
   - Deja seleccionada la velocidad **1,25×**.
   - Cierra la hoja de explicación con la «X».
   - Toca otro ejercicio de la rutina para abrir su explicación.
   - Verifica que el selector de velocidad muestra automáticamente **1,25×** como seleccionado.
   - Pulsa «Escuchar»: el nuevo audio debe comenzar a reproducirse directamente a 1,25×.
4. **Resistencia a Modo Incógnito / Bloqueo de Almacenamiento (AC-5-3):**
   - Abre la aplicación en una pestaña privada/incógnito con bloqueo estricto de almacenamiento local.
   - Pulsa «Escuchar» y cambia la velocidad.
   - La aplicación debe reproducir el audio con la velocidad seleccionada sin lanzar alertas ni pantallas de error de React.
