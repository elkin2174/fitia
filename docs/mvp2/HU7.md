# MVP 2 — HU 7: Iniciar el modo guiado y anunciar ejercicios

Documentación técnica de la implementación frontend de la Historia de Usuario 7 del MVP 2 de FITIA: modo de entrenamiento guiado paso a paso por voz, máquina de estados finita pura, precarga concurrente de audios sin bloqueo de interfaz, anuncio de técnica y cierre de rutina motivacional. Modo estrictamente de **solo lectura**.

> **Estado:** Implementado y probado. 158 pruebas frontend pasando en suite completa (21 nuevas dedicadas a HU 7, HU 9 y HU 10: 12 unitarias en `guidedMachine.test.ts` y 9 de flujo en `guided.test.tsx`). Cero llamadas de red no autorizadas y cero persistencia en base de datos.

---

## 1. Propósito y Alcance

Permite a los estudiantes realizar su sesión de entrenamiento diaria con asistencia sonora continua: la aplicación anuncia cada ejercicio (nombre, series y repeticiones o tiempo de trabajo), reproduce la explicación técnica generada por IA (o respaldo nativo del navegador si no está disponible) y guía las transiciones entre series y descansos sin requerir que el usuario manipule constantemente el dispositivo.

### Criterios de Aceptación
- **AC-7-1:** Al pulsar «Entrenar con voz», la aplicación inicia la sesión en `/hoy/guiado`, anuncia el primer ejercicio (nombre, series y repeticiones o segundos) y lee sus pasos utilizando el audio generado en la HU 3 (con degradación a la voz del dispositivo según HU 6).
- **AC-7-2:** Al abrir el modo guiado, se precarga el audio de todos los ejercicios del día con una concurrencia máxima de 2 peticiones en paralelo sin bloquear el inicio ni la UI. Si el audio del primer ejercicio aún no está listo, muestra «Preparando audio…». Los fallos de precarga no detienen la sesión (conmutan al respaldo del navegador).
- **AC-7-3:** Al terminar la última serie del último ejercicio, la aplicación anuncia el fin de la rutina con la locución fija en español: *«Terminaste la rutina de hoy. ¡Buen trabajo!»* y presenta una pantalla de felicitación.
- **AC-7-4:** El modo es estrictamente de **solo lectura**: no registra sesiones ni puntos, no altera rachas y no envía peticiones `POST`, `PUT`, `PATCH` ni `DELETE` al plan o a la base de datos.

---

## 2. Arquitectura y Componentes Frontend

Se diseñó el subdirectorio `apps/web/src/features/voice/guided/`:

```text
apps/web/src/
├── features/
│   ├── voice/
│   │   ├── guided/
│   │   │   ├── guidedMachine.ts       # Función pura (estado, evento) -> nuevo estado sin efectos
│   │   │   ├── guidedMachine.test.ts  # 12 pruebas unitarias de todas las transiciones y casos límite
│   │   │   ├── useGuidedSession.ts    # Orquestador con precarga concurrente y temporizadores
│   │   │   ├── useWakeLock.ts         # Screen Wake Lock API con reanudación en visibilitychange
│   │   │   └── GuidedPage.tsx         # Pantalla /hoy/guiado conforme a la guía de estilos
│   │   ├── AudioPlayer.ts             # Soporte de preload() concurrente y listener onEnded()
│   │   └── BrowserFallback.ts         # Soporte de listener onEnded() para conmutación fluida
│   └── plan/
│       └── DayRoutine.tsx             # Botón «Entrenar con voz» visible solo en días de entrenamiento listos
└── test/
    └── flows/
        └── guided.test.tsx            # 9 pruebas de integración completas (HU 7, HU 9, HU 10)
```

---

## 3. Máquina de Estados del Modo Guiado (`guidedMachine.ts`)

La máquina es una **función pura** `(state, event) => state` completamente desacoplada de la vista, del DOM y de APIs de audio o temporizadores.

### 3.1 Estados Posibles (`GuidedStatus`)
- `idle`: Modo inactivo o antes de iniciar.
- `announcing`: Anunciando el ejercicio actual (nombre, prescripción y técnica paso a paso).
- `working`: Estudiante realizando la serie (por repeticiones o cuenta regresiva de segundos).
- `resting`: Período de recuperación entre series o ejercicios con cuenta regresiva.
- `paused`: Estado suspendido que recuerda el estado previo (`previousStatus`).
- `finished`: Rutina del día concluida.

### 3.2 Tabla de Transiciones

| Estado Actual | Evento | Estado Siguiente | Comportamiento / Variables de Estado |
|---|---|---|---|
| `idle` | `start` | `announcing` | `exerciseIndex: 0`, `currentSet: 1`, `totalSets: exercises[0].sets`. |
| `announcing` | `speechEnded` | `working` | La locución terminó; inicia la ejecución del ejercicio. |
| `announcing` | `pause` | `paused` | Guarda `previousStatus: "announcing"`. |
| `announcing` | `next` | `announcing` | Avanza a `exerciseIndex + 1`, `currentSet: 1` (si no es el último). |
| `announcing` | `previous` | `announcing` | Retrocede a `exerciseIndex - 1`, `currentSet: 1` (si no es el primero). |
| `announcing` | `repeat` | `announcing` | Reinicia locución del ejercicio actual (`announcementKey++`). |
| `announcing` | `exit` | `idle` | Abandona el modo guiado. |
| `working` | `done` / `timerEnded` | `resting` | Concluye la serie actual e inicia el descanso. |
| `working` | `pause` | `paused` | Guarda `previousStatus: "working"`. |
| `working` | `next` / `previous` | `announcing` | Cambia de ejercicio y pasa a anunciar el nuevo. |
| `working` | `repeat` | `announcing` | Reanuncia el ejercicio actual. |
| `resting` | `timerEnded` / `done` | `announcing` | Si `currentSet < totalSets`: `currentSet: currentSet + 1`.<br>Si `currentSet === totalSets` y hay más ejercicios: `exerciseIndex + 1`, `currentSet: 1`. |
| `resting` | `timerEnded` / `done` | `finished` | Si era la última serie del último ejercicio. |
| `resting` | `pause` | `paused` | Guarda `previousStatus: "resting"`. |
| `resting` | `next` / `previous` | `announcing` | Cambia de ejercicio saltando descansos pendientes. |
| `paused` | `resume` | `previousStatus` | Vuelve exactamente al estado activo previo (`announcing`, `working` o `resting`). |
| `paused` | `next` / `previous` | `announcing` | Cambia de ejercicio y reanuda en anuncio. |
| `paused` | `exit` | `idle` | Abandona el modo guiado. |
| `finished` | `exit` | `idle` | Vuelve a la rutina de hoy. |
| *Cualquiera* | *Evento inválido* | *Mismo estado* | Sin mutaciones ni cambios de referencia. |

---

## 4. Trazabilidad: Criterios de Aceptación vs Pruebas

| Criterio de Aceptación | Descripción | Pruebas Automatizadas |
|---|---|---|
| **AC-7-1** | Con «Entrenar con voz», la app anuncia el primer ejercicio (nombre, series, reps/seg) y lee pasos con audio HU 3. | `apps/web/src/test/flows/guided.test.tsx::AC-7-1: con «Entrenar con voz», la app anuncia el primer ejercicio...` |
| **AC-7-2** | Precarga concurrente de audios del día (máx 2 simultáneos) sin bloquear la interfaz. | `apps/web/src/test/flows/guided.test.tsx::AC-7-2: al iniciar se precarga el audio de los ejercicios del día...` |
| **AC-7-3** | Al terminar el último ejercicio anuncia fin de rutina con locución fija y muestra felicitación. | `apps/web/src/test/flows/guided.test.tsx::AC-7-3: al terminar el último ejercicio anuncia el fin de rutina...` |
| **AC-7-4** | Modo estrictamente de solo lectura (cero peticiones de escritura). | `apps/web/src/test/flows/guided.test.tsx::AC-7-4: el modo es estrictamente de solo lectura...` |
| **Transiciones Puras** | Cobertura integral de la máquina de estados. | `apps/web/src/features/voice/guided/guidedMachine.test.ts` (12 pruebas unitarias) |

---

## 5. Guía de Prueba Manual (Dispositivo Móvil / Celular Real)

### Requisitos Previos
1. Celular conectado en la misma red local que la máquina de desarrollo.
2. Iniciar sesión con un usuario con diagnóstico completado y plan generado (`/hoy`).

### Pasos de Verificación
1. **Acceso al modo:**
   - Abre la pestaña **Hoy** en el móvil.
   - Verifica que aparece el botón primario con ícono de micrófono **«Entrenar con voz»**.
   - Toca el botón: la URL cambia a `/hoy/guiado`.
2. **Anuncio y reproducción del primer ejercicio (AC-7-1):**
   - El dispositivo anuncia el nombre del ejercicio (ej. *«Sentadilla con peso corporal. 3 series, 10 repeticiones»*).
   - Inmediatamente después, se reproduce el audio explicativo de la técnica paso a paso.
   - Si la red es lenta, se aprecia brevemente el indicador *«Preparando audio…»* sin congelar la pantalla.
3. **Flujo completo y fin de rutina (AC-7-3):**
   - Completa las series pulsando «Terminar serie» y «Saltar descanso» (o esperando el temporizador).
   - Al terminar la última serie del último ejercicio, la pantalla muestra la tarjeta de felicitación *«¡Rutina completada!»* y se escucha claramente: *«Terminaste la rutina de hoy. ¡Buen trabajo!»*.
4. **Verificación de solo lectura (AC-7-4):**
   - Regresa a `/perfil`: verifica que los puntos y el nivel no sufrieron alteraciones indebidas.
