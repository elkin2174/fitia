# MVP 2 — HU 4: Pausar, reanudar y repetir el audio

Documentación técnica de la implementación frontend de la Historia de Usuario 4 del MVP 2 de FITIA: controles interactivos de reproducción (pausa, reanudación y repetición), estados habilitados/deshabilitados según el ciclo de vida del audio y soporte de navegación por teclado.

> **Estado:** Implementado y probado. 123 pruebas frontend pasando en suite completa (24 nuevas dedicadas a HU3, HU4 y HU5). Cero llamadas a servicios de audio reales en pruebas automatizadas.

---

## 1. Propósito y Alcance

Permite a los estudiantes controlar la reproducción de la explicación sonora a su propio ritmo durante el entrenamiento mediante acciones de pausa, reanudación y reinicio.

### Criterios de Aceptación
- **AC-4-1:** Pausar detiene la reproducción conservando la posición actual (`currentTime`); reanudar continúa la reproducción exactamente desde donde quedó.
- **AC-4-2:** «Repetir» reinicia el audio del ejercicio desde el segundo cero (`currentTime = 0`).
- **AC-4-3:** Sin audio en curso (estado inicial `idle`, en carga o con error), los botones de pausa/reanudar y repetir se encuentran deshabilitados (`disabled` y opacidad reducida).
- **AC-4-4:** Todos los controles de reproducción son totalmente operables mediante teclado (teclas Tab, Enter y Espacio), con anillos de enfoque visibles conformes a WCAG 2.1 AA.

---

## 2. Arquitectura y Componentes Frontend

Los controles forman parte de `PlaybackControls.tsx` dentro de `apps/web/src/features/voice/`:

```text
apps/web/src/
└── features/
    └── voice/
        ├── PlaybackControls.tsx    # Controles de reproducción y velocidad
        └── AudioPlayer.ts          # Métodos pause(), resume() y restart()
```

### Comportamiento del Estado de Reproducción
- **Botón Dinámico Pausar / Reanudar:**
  - Cuando el audio está reproduciéndose (`isPlaying === true`), el botón muestra la etiqueta **«Pausar»** junto con el ícono de dos barras verticales (`||`).
  - Cuando el audio está en pausa o finalizó (`isPlaying === false`), muestra la etiqueta **«Reanudar»** con el ícono de triángulo de reproducción (`▶`).
  - Al hacer clic en «Pausar», se invoca `audioPlayer.pause()`, cambiando el estado a `paused`.
  - Al hacer clic en «Reanudar», se invoca `audioPlayer.resume()`, reanudando el audio con `audio.play()`. Si el audio había finalizado (`ended === true`), se rebobina automáticamente al inicio.
- **Botón Repetir:**
  - Invoca `audioPlayer.restart()`, el cual fija `audio.currentTime = 0`, mantiene la velocidad configurada y ejecuta `audio.play()`.
- **Accesibilidad y Foco:**
  - Todos los botones cuentan con atributo `type="button"`, etiquetas explícitas en español y estilo de foco `focus-visible:outline-2 focus-visible:outline-focus`.

---

## 3. Trazabilidad: Criterios de Aceptación vs Pruebas

| Criterio de Aceptación | Descripción | Pruebas Automatizadas |
|---|---|---|
| **AC-4-1** | Pausa y reanudar continúan desde donde quedó sin perder posición. | `apps/web/src/test/flows/voice.test.tsx::AC-4-1 a AC-4-3: pausa, reanudar, repetir y estado deshabilitado sin audio`<br>`apps/web/src/features/voice/AudioPlayer.test.ts::AC-4-1 y AC-4-2` |
| **AC-4-2** | «Repetir» reinicia el audio fijando `currentTime = 0` y volviendo a reproducir. | `apps/web/src/test/flows/voice.test.tsx::AC-4-1 a AC-4-3: pausa, reanudar, repetir y estado deshabilitado sin audio`<br>`apps/web/src/features/voice/AudioPlayer.test.ts::AC-4-1 y AC-4-2` |
| **AC-4-3** | Sin audio en curso, los botones de pausa/reanudar y repetir están deshabilitados. | `apps/web/src/test/flows/voice.test.tsx::AC-4-1 a AC-4-3: pausa, reanudar, repetir y estado deshabilitado sin audio` |
| **AC-4-4** | Los controles son operables mediante teclado (Enter y Espacio) con foco visible. | `apps/web/src/test/flows/voice.test.tsx::AC-4-4: los controles se operan con teclado` |

---

## 4. Guía de Prueba Manual (Dispositivo Móvil / Celular Real)

### Requisitos Previos
1. Abrir la aplicación en un celular real y acceder a `/hoy`.
2. Seleccionar un ejercicio para abrir el `BottomSheet`.

### Pasos de Verificación
1. **Verificación de Estado Inicial Deshabilitado (AC-4-3):**
   - Antes de presionar «Escuchar», inspecciona visualmente los botones «Reanudar» y «Repetir».
   - Deben verse atenuados (opacidad reducida) y al tocarlos no debe ocurrir ninguna acción.
2. **Pausa y Reanudación (AC-4-1):**
   - Pulsa «Escuchar». Deja reproducir 3 a 5 segundos de la explicación.
   - Pulsa el botón «Pausar» (ícono `||`). El sonido debe detenerse de inmediato y el botón cambia a «Reanudar».
   - Espera unos segundos y pulsa «Reanudar». La voz debe continuar exactamente en la palabra o frase donde se detuvo, sin empezar desde el inicio.
3. **Repetición (AC-4-2):**
   - Mientras el audio va por la mitad, pulsa el botón «Repetir» (ícono circular de reinicio).
   - El audio debe reiniciarse inmediatamente desde el título y el Paso 1.
4. **Operación con Teclado (Accesibilidad AC-4-4):**
   - Con un teclado físico o emulador de accesibilidad, navega con la tecla `Tab` hasta el botón «Escuchar».
   - Presiona `Enter` para iniciar el audio.
   - Navega con `Tab` al botón «Pausar» y presiona la barra espaciadora: el audio se pausa correctamente.
