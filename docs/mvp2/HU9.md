# MVP 2 — HU 9: Controlar el modo guiado con botones

Documentación técnica de la implementación frontend de la Historia de Usuario 9 del MVP 2 de FITIA: barra de controles táctiles y accesibles para la navegación entre ejercicios («Anterior», «Siguiente»), control de reproducción y temporizadores («Pausar», «Continuar», «Repetir») y salida segura del modo guiado («Salir»).

> **Estado:** Implementado y probado. 158 pruebas frontend pasando en suite completa (21 nuevas dedicadas a HU 7, HU 9 y HU 10). Cumplimiento de WCAG 2.1 AA en contraste, tamaño táctil y navegación con teclado.

---

## 1. Propósito y Alcance

Proporciona al usuario el control absoluto de su ritmo de entrenamiento durante la sesión guiada por voz. Permite pausar ante cualquier imprevisto, repetir explicaciones complejas, saltar o retroceder ejercicios y abandonar la sesión sin dejar procesos de audio o temporizadores en segundo plano.

### Criterios de Aceptación
- **AC-9-1:** «Siguiente» y «Anterior» permiten cambiar de ejercicio. Al activarse, detienen de inmediato cualquier audio en reproducción o locución en curso y reinician el anuncio del nuevo ejercicio. En el primer ejercicio «Anterior» está deshabilitado; en el último ejercicio «Siguiente» está deshabilitado.
- **AC-9-2:** «Pausar» detiene el audio activo y congela los temporizadores (sea de serie por tiempo o de descanso). «Continuar» retoma la locución o reanuda la cuenta regresiva exactamente desde el segundo donde se detuvo.
- **AC-9-3:** «Repetir» vuelve a reproducir la locución y explicación técnica del ejercicio actual desde el principio.
- **AC-9-4:** «Salir» detiene todos los audios y temporizadores en vuelo, libera la pantalla activa (Wake Lock) y redirige de forma segura a la rutina de hoy (`/hoy`).
- **AC-9-5:** Todos los botones tienen etiquetas en español, nombres accesibles (`aria-label`), estilos de foco visible (`focus-visible:outline-2`) y dimensiones táctiles conformes a estándares móviles (≥ 44 px de altura).

---

## 2. Arquitectura e Interacción de Controles

Los controles se gestionan reactivamente mediante el hook [`useGuidedSession.ts`](file:///c:/Users/elkin/Documentos/Universidad/2026-II/Integrador 2/Fit-AI/apps/web/src/features/voice/guided/useGuidedSession.ts) y se renderizan en la sección inferior de [`GuidedPage.tsx`](file:///c:/Users/elkin/Documentos/Universidad/2026-II/Integrador 2/Fit-AI/apps/web/src/features/voice/guided/GuidedPage.tsx):

```text
apps/web/src/
└── features/
    └── voice/
        └── guided/
            ├── GuidedPage.tsx       # Barra de navegación accesible: Anterior, Pausar/Continuar, Repetir, Siguiente y Salir
            ├── useGuidedSession.ts  # Despacho de eventos next, previous, pause, resume, repeat, exit y done
            └── guidedMachine.ts     # Transiciones seguras y retención de previousStatus durante la pausa
```

### 2.1 Comportamiento Detallado de Cada Control

- **Botón «Anterior»:**
  - Deshabilitado (`disabled`) cuando `exerciseIndex === 0`.
  - Al pulsar, invoca `previous()`: cancela el habla sintética (`speechSynthesis.cancel()`), detiene el reproductor de audio (`player.stop()`) y transiciona la máquina a `exerciseIndex - 1` en estado `announcing`.
- **Botón Dinámico «Pausar» / «Continuar»:**
  - Cuando el modo está activo (en `announcing`, `working` o `resting`), muestra **«Pausar»** con variante visual secundaria y el ícono de pausa (`||`). Al pulsar, congela los temporizadores activos (`clearInterval`), pausa el audio/síntesis y transiciona a `paused` recordando el estado previo en `previousStatus`.
  - Cuando el modo está en pausa (`status === "paused"`), conmuta a **«Continuar»** con variante primaria y el ícono de reproducción (`▶`). Al pulsar, restaura el estado previo (`previousStatus`) y reanuda el audio o la cuenta regresiva desde los segundos restantes.
- **Botón «Repetir»:**
  - Al pulsar, invoca `repeat()`: detiene cualquier audio o temporizador activo, incrementa la clave reactiva `announcementKey` y fuerza a la sesión a reanunciar el ejercicio actual y sus pasos técnicos desde el inicio.
- **Botón «Siguiente»:**
  - Deshabilitado (`disabled`) cuando `exerciseIndex === exercises.length - 1`.
  - Al pulsar, invoca `next()`: detiene audios, cancela la cola y avanza inmediatamente al siguiente ejercicio en estado `announcing`.
- **Botón «Salir»:**
  - Ubicado en la barra superior con ícono de flecha hacia la izquierda y etiqueta «Salir».
  - Al pulsar, invoca `exit()`, aborta las peticiones de precarga pendientes, apaga el audio y navega limpiamente a `/hoy`.

---

## 3. Trazabilidad: Criterios de Aceptación vs Pruebas

| Criterio de Aceptación | Descripción | Pruebas Automatizadas |
|---|---|---|
| **AC-9-1** | «Siguiente» y «Anterior» navegan entre ejercicios, respetan límites y cancelan audio. | `apps/web/src/test/flows/guided.test.tsx::AC-9-1 a AC-9-5: control por botones («Siguiente», «Anterior», «Pausar», «Continuar», «Repetir», «Salir»)`<br>`apps/web/src/features/voice/guided/guidedMachine.test.ts::navegación con next y previous respeta los límites` |
| **AC-9-2** | «Pausar» detiene audio y temporizador; «Continuar» los reanuda sin perder posición. | `apps/web/src/test/flows/guided.test.tsx::AC-9-1 a AC-9-5...`<br>`apps/web/src/features/voice/guided/guidedMachine.test.ts::pausa y reanudación desde cada estado activo` |
| **AC-9-3** | «Repetir» reanuncia el ejercicio actual desde el principio. | `apps/web/src/test/flows/guided.test.tsx::AC-9-1 a AC-9-5...`<br>`apps/web/src/features/voice/guided/guidedMachine.test.ts::repeat reinicia announcing en el ejercicio actual` |
| **AC-9-4** | «Salir» detiene todo y redirige a `/hoy`. | `apps/web/src/test/flows/guided.test.tsx::AC-9-1 a AC-9-5...`<br>`apps/web/src/features/voice/guided/guidedMachine.test.ts::exit desde cualquier estado regresa a idle` |
| **AC-9-5** | Botones con textos claros en español, nombres accesibles y operabilidad con teclado. | `apps/web/src/test/flows/guided.test.tsx::AC-9-1 a AC-9-5...` |

---

## 4. Guía de Prueba Manual (Dispositivo Móvil / Celular Real)

### Requisitos Previos
1. Celular conectado y con sesión iniciada en `/hoy`.
2. Presionar «Entrenar con voz» para ingresar a `/hoy/guiado`.

### Pasos de Verificación
1. **Navegación Inicial y Límites (AC-9-1):**
   - Comprueba que en el primer ejercicio el botón **«Anterior»** aparece atenuado y no reacciona al tacto.
   - Pulsa **«Siguiente»**: la voz se interrumpe al instante y la pantalla muestra de inmediato el segundo ejercicio.
   - En el último ejercicio, comprueba que **«Siguiente»** queda deshabilitado y **«Anterior»** se habilita.
2. **Pausa y Reanudación (AC-9-2):**
   - Durante una serie por tiempo (ej. Plancha) o durante un descanso con temporizador visible, toca **«Pausar»**.
   - El segundero debe detenerse en seco y el panel central muestra la insignia roja *«Pausado»*.
   - El botón cambia visualmente a rojo primario con la etiqueta **«Continuar»**.
   - Toca **«Continuar»**: el segundero vuelve a decrementar fluidamente desde el segundo exacto donde se congeló.
3. **Repetición (AC-9-3):**
   - Pulsa **«Repetir»**: el audio del ejercicio se reinicia desde el nombre y vuelve a relatar los pasos de técnica.
4. **Salida Limpia (AC-9-4):**
   - Pulsa **«Salir»** en la esquina superior izquierda: regresas inmediatamente a la vista `/hoy`. Comprueba que ningún sonido sigue reproduciéndose en el fondo.
