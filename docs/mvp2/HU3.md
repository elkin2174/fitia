# MVP 2 — HU 3: Escuchar la explicación de un ejercicio

Documentación técnica de la implementación frontend de la Historia de Usuario 3 del MVP 2 de FITIA: reproducción de audio explicativo de técnica mediante síntesis de voz, estado de carga reactivo, control de concurrencia y limpieza de recursos.

> **Estado:** Implementado y probado. 123 pruebas frontend pasando en suite completa (24 nuevas dedicadas a HU3, HU4 y HU5). Cero llamadas a servicios de audio reales en pruebas automatizadas (uso de MSW y mocks deterministas de `HTMLMediaElement`).

---

## 1. Propósito y Alcance

Permite a los estudiantes escuchar la explicación guiada en audio de la técnica de cualquier ejercicio desde la hoja inferior de detalles (`ExerciseGuideSheet`).

### Criterios de Aceptación
- **AC-3-1:** Al pulsar «Escuchar» se reproduce el audio explicativo en español del ejercicio.
- **AC-3-2:** Mientras se genera el audio en el servidor se muestra «Preparando audio…» y el botón queda deshabilitado para evitar peticiones duplicadas.
- **AC-3-3:** La primera reproducción puede tardar hasta 5 segundos (síntesis de Gemini TTS en el backend); las siguientes del mismo ejercicio inician en ≤ 1 segundo gracias a la caché de blobs en memoria.
- **AC-3-4:** Si el usuario cierra la hoja de explicación o cambia de ejercicio, la reproducción se detiene inmediatamente y se liberan los controladores en vuelo.
- **AC-3-5:** Nunca suenan dos audios simultáneamente (garantizado mediante una única instancia de `HTMLAudioElement` a nivel de aplicación).
- **AC-3-6:** Botón y mensajes con textos claros en español y nombres accesibles para tecnologías de asistencia (WAI-ARIA).

---

## 2. Arquitectura y Componentes Frontend

Se diseñó el módulo `apps/web/src/features/voice/` siguiendo los principios de arquitectura modular y desacoplamiento de la interfaz:

```text
apps/web/src/
├── features/
│   ├── voice/
│   │   ├── api.ts                  # fetchExerciseAudio: petición GET con credentials: "include" y parsing de WAV / ApiError
│   │   ├── AudioPlayer.ts          # Singleton de control de HTMLAudioElement y caché LRU de Object URLs
│   │   ├── useExerciseAudio.ts     # Hook reactivo basado en useSyncExternalStore
│   │   ├── ListenButton.tsx        # Botón «Escuchar» con estado de carga «Preparando audio…»
│   │   ├── PlaybackControls.tsx    # Controles de pausar/reanudar, repetir y selector de velocidad
│   │   └── playbackRate.ts         # Persistencia en localStorage con fallback seguro
│   └── plan/
│       └── ExerciseGuideSheet.tsx  # Integración sin alterar el diseño existente de pasos ni aviso
└── test/
    └── flows/
        └── voice.test.tsx          # Pruebas de integración de flujo completo
```

### Componentes Clave
- **`fetchExerciseAudio(exerciseId)` (`features/voice/api.ts`):** Realiza una solicitud `GET /api/v1/plan/exercises/${exerciseId}/audio` con `Accept: "audio/wav, application/json"` y `credentials: "include"`. Si el servidor responde con error (`503 AI_UNAVAILABLE`, `429`, etc.), normaliza la respuesta a una instancia de `ApiError`. Si responde exitosamente (`200 OK`), entrega un `Blob`.
- **`AudioPlayer` (`features/voice/AudioPlayer.ts`):** Administrador de audio con patrón Singleton (`globalAudioPlayer`). Gestiona un único elemento `HTMLAudioElement` en el DOM, previene solapamiento de pistas, almacena hasta 50 blobs en memoria mediante `URL.createObjectURL`, y libera memoria con `URL.revokeObjectURL` al desalojar entradas o detener el reproductor.
- **`useExerciseAudio(exerciseId)` (`features/voice/useExerciseAudio.ts`):** Hook que suscribe el componente a los cambios de estado de `AudioPlayer` (`idle | loading | playing | paused | error`) mediante `useSyncExternalStore`, garantizando renderizados eficientes y evitando bucles de actualización.
- **`ListenButton` (`features/voice/ListenButton.tsx`):** Control primario accesible con ícono SVG de altavoz, texto visible «Escuchar» y estado de carga «Preparando audio…» con spinner y atributo `aria-busy`.

---

## 3. Trazabilidad: Criterios de Aceptación vs Pruebas

| Criterio de Aceptación | Descripción | Pruebas Automatizadas |
|---|---|---|
| **AC-3-1** | Pulsar «Escuchar» solicita el audio al backend y ejecuta `play()`. | `apps/web/src/test/flows/voice.test.tsx::AC-3-1: al pulsar «Escuchar» se pide el audio y se llama a play`<br>`apps/web/src/features/voice/AudioPlayer.test.ts::AC-3-1` |
| **AC-3-2** | Mientras se genera muestra «Preparando audio…» y clics repetidos no lanzan peticiones duplicadas. | `apps/web/src/test/flows/voice.test.tsx::AC-3-2: durante la carga aparece «Preparando audio…» y clics repetidos no duplican peticiones`<br>`apps/web/src/features/voice/AudioPlayer.test.ts::AC-3-2` |
| **AC-3-3** | Segunda reproducción del mismo ejercicio usa caché en memoria y no reenvía la petición. | `apps/web/src/test/flows/voice.test.tsx::AC-3-3: la segunda reproducción del mismo ejercicio no vuelve a pedir el audio (caché en memoria)`<br>`apps/web/src/features/voice/AudioPlayer.test.ts::AC-3-3` |
| **AC-3-4** | Cerrar la hoja de explicación detiene inmediatamente el audio. | `apps/web/src/test/flows/voice.test.tsx::AC-3-4: cerrar la explicación detiene el audio` |
| **AC-3-5** | Nunca suenan dos audios simultáneamente; iniciar otro detiene el anterior. | `apps/web/src/test/flows/voice.test.tsx::AC-3-5: nunca suenan dos audios a la vez; iniciar otro detiene el anterior`<br>`apps/web/src/features/voice/AudioPlayer.test.ts::AC-3-5` |
| **AC-3-6** | Textos en español y nombres accesibles en botones y mensajes. | `apps/web/src/test/flows/voice.test.tsx::AC-3-6: los botones y mensajes están en español y tienen nombre accesible` |
| **Resiliencia 503** | Error `AI_UNAVAILABLE` muestra banner en español y botón de reintento. | `apps/web/src/test/flows/voice.test.tsx::error 503 AI_UNAVAILABLE muestra mensaje en español y permite reintentar` |

---

## 4. Guía de Prueba Manual (Dispositivo Móvil / Celular Real)

### Requisitos Previos
1. Backend de FITIA corriendo en la red local o en Render.
2. Frontend ejecutándose con `npm run dev -- --host` para acceder desde la IP local en un celular real.
3. Usuario con sesión iniciada y plan activo en `/hoy`.

### Pasos de Verificación
1. **Apertura de la Guía:**
   - Toca cualquier tarjeta de ejercicio en la rutina de hoy.
   - Verifica que se abre el `BottomSheet` con el título del ejercicio, el botón «Escuchar» en la parte superior, los pasos numerados y el aviso orientativo.
2. **Primera Reproducción (Generación):**
   - Pulsa el botón «Escuchar».
   - Observa que el botón cambia a «Preparando audio…», se deshabilita y muestra un spinner de carga.
   - Toca repetidamente el botón mientras carga: no debe disparar peticiones adicionales ni producir errores.
   - En ≤ 5 segundos, el audio comienza a reproducirse con pronunciación clara en español.
3. **Segunda Reproducción (Caché):**
   - Pulsa «Pausar» y luego «Reanudar».
   - La reanudación o repetición debe comenzar de forma inmediata (≤ 1 s) sin latencia perceptible de red.
4. **Detención por Cierre:**
   - Mientras el audio suena, toca la «X» de cerrar la hoja o el fondo oscurecido.
   - El audio debe silenciarse instantáneamente. Al volver a abrir el ejercicio, el audio permanece en pausa hasta que el usuario decida reproducirlo de nuevo.
5. **Concurrencia entre Ejercicios:**
   - Inicia el audio de un ejercicio.
   - Cierra la hoja y abre otro ejercicio diferente.
   - Pulsa «Escuchar» en el nuevo ejercicio: el audio anterior no debe continuar sonando de fondo.
