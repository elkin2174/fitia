# MVP 2 — HU 8: Descansos con cuenta regresiva y avisos de voz

Documentación técnica de la implementación full stack (FastAPI backend + React 19 frontend) de la Historia de Usuario 8 del MVP 2 de FITIA: cuenta regresiva de descanso visible basada en timestamp (inmune a retrasos por pestañas en segundo plano), avisos por voz generados por IA mediante catálogo cerrado de frases fijas cacheadas en memoria, y degradación fluida a la voz nativa del dispositivo.

> **Estado:** Implementado y probado. 5 pruebas de integración backend nuevas en `test_plan_audio_cues.py` (13 pruebas de audio backend pasando en total) y 6 pruebas de flujo frontend nuevas en `guided.test.tsx` (164 pruebas frontend pasando en suite completa). Sin migraciones de base de datos ni persistencia de audios.

---

## 1. Propósito y Alcance

Permite a los estudiantes sincronizar sus descansos entre series y ejercicios durante el modo guiado sin tener que mirar la pantalla constantemente: la aplicación presenta un temporizador visible con el tiempo prescrito en el plan, emite avisos sonoros al iniciar el descanso, a los 10 segundos restantes (si el descanso supera dicha duración) y al finalizar el descanso, asegurando que la locución del siguiente ejercicio no se solape con el aviso de fin de descanso.

### Criterios de Aceptación
- **AC-8-1:** Entre series y ejercicios corre una cuenta regresiva visible con el tiempo de descanso (`rest_seconds`) del plan. El cálculo se basa en marca de tiempo objetivo (`targetEndTime = Date.now() + remaining * 1000`) para evitar desincronización o retrasos cuando la pestaña o aplicación pasa a segundo plano.
- **AC-8-2:** La aplicación avisa por voz a los 10 s y al terminar el descanso, utilizando frases fijas cortas obtenidas mediante `GET /api/v1/plan/audio/cues/{name}`, generadas por IA y cacheadas en memoria. Si el descanso original es $\le 10\text{ s}$, no se duplica el aviso de 10 s. La frase `fin-rutina` anuncia el fin de la rutina diaria. La locución del siguiente ejercicio espera a que concluya el audio de `fin-descanso` antes de iniciar (cero solapamiento).
- **AC-8-3:** Catálogo cerrado de frases en el backend (`descanso`, `diez-segundos`, `fin-descanso`, `fin-rutina`). Cualquier otro nombre o intento de path traversal devuelve `404 CUE_NOT_FOUND`. Sin sesión devuelve `401 UNAUTHORIZED`.
- **AC-8-4:** Si el audio con IA de una frase fija falla (código 503 `AI_UNAVAILABLE`, desconexión o timeout), la aplicación degrada de forma transparente a la síntesis de voz del navegador utilizando el texto local oficial en español.
- **Control de Navegación:** Pausar durante el descanso congela el temporizador y conserva los segundos restantes; continuar retoma la cuenta regresiva desde ese punto exacto. «Saltar descanso», «Siguiente», «Anterior» y «Salir» cancelan de inmediato cualquier audio en reproducción o temporizador activo.

---

## 2. Catálogo Cerrado de Frases (Cues)

El catálogo es estricto y reside tanto en el backend (`apps/api/app/ai/use_cases/audio_cues.py`) como en el frontend (`apps/web/src/features/voice/cues.ts`):

| Nombre (`name`) | Locución en Español (Texto Oficial) | Momento de Activación |
|---|---|---|
| `descanso` | *"Descansa y recupera el aliento."* | Al ingresar al estado de descanso entre series o ejercicios. |
| `diez-segundos` | *"Quedan diez segundos."* | Cuando el descanso restante llega a 10 s (solo si el descanso original es $> 10\text{ s}$). |
| `fin-descanso` | *"Termina el descanso. ¡A seguir!"* | Al alcanzar 0 s de descanso; la rutina espera su conclusión para anunciar el siguiente ejercicio. |
| `fin-rutina` | *"Terminaste la rutina de hoy. ¡Buen trabajo!"* | Al completar la última serie del último ejercicio de la sesión diaria. |

---

## 3. Arquitectura y Componentes Full Stack

### 3.1 Backend (`apps/api`)
- **`app/ai/use_cases/audio_cues.py`:** Definición del diccionario inmutable `AUDIO_CUES` y función de consulta `get_cue_text(name: str) -> str | None`.
- **`app/modules/plan/service.py` (`PlanService.get_cue_audio`):**
  - Valida pertenencia al catálogo cerrado (`404 CUE_NOT_FOUND` si no existe).
  - Aplica control de frecuencia por usuario (`f"plan:audio:{user_id}"` con cuota de `Settings.RATE_LIMIT_EXERCISE_AUDIO_PER_USER`).
  - Genera clave SHA-256 (`make_cache_key`) a partir del modelo, la voz y el texto estático.
  - Consulta y almacena en la caché LRU en memoria de proceso (`AudioCache`); las peticiones subsiguientes de cualquier estudiante no llaman a la IA externa.
  - Delega en `AIGateway.synthesize(use_case="cue_audio", text=...)` protegido por circuit breaker y presupuesto de tiempo.
  - Captura `AIFailure` y responde con `503 AI_UNAVAILABLE`.
- **`app/modules/plan/router.py` (`GET /audio/cues/{name:path}`):** Endpoint autenticado con sesión (`CurrentUser = Depends(require_complete_profile)`), devuelve `200 OK` con `Content-Type: audio/wav` y encabezado `Cache-Control: private, max-age=86400`.
- **`tests/integration/test_plan_audio_cues.py`:** Suite de pruebas con adaptador de síntesis falso (`FakeSpeechAdapter`), verificando formato WAV, caché compartida, catálogo cerrado, circuit breaker, rate limit y no persistencia en BD (NFR-26).

### 3.2 Frontend (`apps/web`)
- **`features/voice/api.ts` (`fetchCueAudio`):** Petición `GET /api/v1/plan/audio/cues/{name}` con credenciales de sesión (`credentials: "include"`) y manejo de `AbortSignal`.
- **`features/voice/AudioPlayer.ts` (`playCue` y `preloadCue`):** Métodos dedicados para reproducir frases fijas a través del reproductor global compartido (`globalAudioPlayer`), garantizando que nunca suenen dos audios al mismo tiempo (AC-3-5) y cacheando blobs WAV localmente.
- **`features/voice/cues.ts`:**
  - `AUDIO_CUES_TEXT`: Diccionario de frases oficiales en español.
  - `playCueWithFallback`: Intenta reproducir el audio generado por IA; si falla (red, 503 o timeout), conmuta fluidamente a `speechSynthesis` del navegador.
  - `preloadCues`: Precarga en segundo plano las 4 frases fijas al iniciar la sesión.
- **`features/voice/guided/useGuidedSession.ts`:**
  - Temporizador basado en marcas de tiempo (`Date.now()`) con refresco continuo (250 ms) para evitar desincronización en pestañas en segundo plano.
  - Disparo de aviso inicial (`descanso`), aviso a 10 s (`diez-segundos` con guardia para descansos $\le 10\text{ s}$) y fin de descanso (`fin-descanso`).
  - Sincronización asíncrona: `dispatch({ type: "timerEnded" })` espera activamente a que termine el audio de `fin-descanso` antes de transicionar a `announcing`, evitando solapamientos.
  - Congelación del tiempo restante al pausar (`pausedRemainingRef`) y reanudación exacta al continuar.
  - Cancelación inmediata de audios y temporizadores en acciones de navegación (`next`, `previous`, `done`, `repeat`, `exit`).

---

## 4. Trazabilidad: Criterios de Aceptación vs Pruebas

| Criterio de Aceptación | Descripción | Pruebas Automatizadas |
|---|---|---|
| **AC-8-1** | Cuenta regresiva visible con tiempo de descanso del plan basada en timestamp. | `apps/web/src/test/flows/guided.test.tsx::AC-8-1: cuenta regresiva de descanso visible y decreciendo...`<br>`apps/web/src/test/flows/guided.test.tsx::Pausar en descanso detiene el temporizador y reanudar retoma...` |
| **AC-8-2** | Avisos por voz de descanso, diez segundos y fin de descanso con frases fijas (sin solapamiento). | `apps/api/tests/integration/test_plan_audio_cues.py::test_ac_8_2_todos_los_cues_validos_y_formato_wav`<br>`apps/api/tests/integration/test_plan_audio_cues.py::test_ac_8_2_cache_en_memoria_y_compartida_entre_usuarios`<br>`apps/web/src/test/flows/guided.test.tsx::AC-8-2: avisos por voz de descanso, diez segundos y fin de descanso...`<br>`apps/web/src/test/flows/guided.test.tsx::AC-8-2: si el descanso original es <= 10 s, no se duplica el aviso de 10 s` |
| **AC-8-3** | Catálogo cerrado; nombres desconocidos o path traversal devuelven 404; 401 sin sesión; 403 sin perfil. | `apps/api/tests/integration/test_plan_audio_cues.py::test_ac_8_3_catalogo_cerrado_y_errores_404_401_403` |
| **AC-8-4** | Degradación a voz del navegador si el audio de una frase fija falla (503 AI_UNAVAILABLE o desconexión). | `apps/api/tests/integration/test_plan_audio_cues.py::test_ac_8_4_degradacion_503_proveedor_fallido_o_desactivado`<br>`apps/web/src/test/flows/guided.test.tsx::AC-8-4: si el audio del cue falla (503 AI_UNAVAILABLE), degrada a la voz del navegador...` |
| **NFR-26** | Cero persistencia de audios en la base de datos (footprint de usuario intacto). | `apps/api/tests/integration/test_plan_audio_cues.py::test_nfr_26_sin_persistencia_en_bd_y_rate_limit` |
| **NFR-27** | Privacidad: ningún identificador del estudiante viaja al proveedor de síntesis. | `apps/api/tests/integration/test_plan_audio_cues.py::test_ac_8_2_todos_los_cues_validos_y_formato_wav` |
| **NFR-30** | Control de costo mediante limitador de tasa (`429 RATE_LIMITED`) y circuit breaker. | `apps/api/tests/integration/test_plan_audio_cues.py::test_nfr_26_sin_persistencia_en_bd_y_rate_limit`<br>`apps/api/tests/integration/test_plan_audio_cues.py::test_ac_8_4_degradacion_503_proveedor_fallido_o_desactivado` |

---

## 5. Guía de Prueba Manual

### Requisitos Previos
1. Servidor backend en ejecución (`uvicorn app.main:app`).
2. Cliente web en ejecución (`npm run dev --prefix apps/web`).
3. Estudiante autenticado con perfil completo y rutina de entrenamiento activa para hoy.

### Pasos de Verificación Manual
1. **Inicio del modo guiado y descanso:**
   - En `/hoy`, presionar «Entrenar con voz».
   - Tras el anuncio del primer ejercicio, presionar «Terminar serie» para concluir la serie 1.
   - **Resultado esperado:** La pantalla cambia al estado `Descanso`, mostrando el temporizador de descanso del plan (ej. `30 s`). De inmediato se escucha la locución: *«Descansa y recupera el aliento.»*.
2. **Cuenta regresiva y aviso a los 10 segundos:**
   - Observar el decremento fluido del reloj segundo a segundo.
   - Al marcar `10 s`, escuchar atentamente.
   - **Resultado esperado:** Se reproduce la frase *«Quedan diez segundos.»* mientras el segundero sigue corriendo hacia cero.
3. **Fin de descanso y transición limpia:**
   - Esperar a que el contador llegue a `0 s`.
   - **Resultado esperado:** Se escucha la frase *«Termina el descanso. ¡A seguir!»*. Justo después de terminar esta frase, la pantalla y el audio pasan automáticamente a anunciar la siguiente serie (*«Serie 2 de ...»*), sin interrupciones ni voces solapadas.
4. **Pausa y reanudación durante el descanso:**
   - En el siguiente descanso, presionar «Pausar» cuando resten, por ejemplo, `18 s`.
   - Verificar que el contador se detiene en `18 s` y la pantalla muestra «Entrenamiento en pausa».
   - Esperar varios segundos y presionar «Continuar».
   - **Resultado esperado:** El temporizador continúa desde `18 s` y no se reinicia a `30 s`. Tampoco se reanuncia *«Descansa y recupera el aliento.»*.
5. **Saltar descanso:**
   - Durante un descanso, pulsar «Saltar descanso».
   - **Resultado esperado:** El descanso y cualquier locución activa se cortan inmediatamente y la rutina avanza de inmediato a la siguiente serie/ejercicio.
6. **Verificación de catálogo cerrado en backend:**
   - En una terminal o cliente HTTP, solicitar con la cookie de sesión:
     `GET /api/v1/plan/audio/cues/frase-invalida`
   - **Resultado esperado:** Código `404 Not Found` con cuerpo uniforme:
     `{"error": {"code": "CUE_NOT_FOUND", "message": "La frase de audio solicitada no existe.", "fields": []}}`.
