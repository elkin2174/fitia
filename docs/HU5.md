# HU 5 — Generación del plan semanal con IA

Documentación de la implementación backend de la HU 5 del MVP FITIA: qué se construyó, cómo funciona, cómo se probó y cómo probarlo a mano. Se apoya en [H1.md](H1.md), [HU2.md](HU2.md), [HU3.md](HU3.md) y [HU4.md](HU4.md).

> Estado: implementado y probado. 504 pruebas pasando (296 de HU 1–4 + 208 nuevas) en Python 3.14 local y 3.11 en Docker; ninguna llama a Gemini. Verificado además contra **Gemini real** (`gemini-3.8-flash`) con el script de humo y con un recorrido completo por la API. Sin commit todavía (la HU 4 tampoco tiene commit). Nueva migración `0003_hu5_plan_schema` (con `downgrade`, probada arriba-abajo-arriba).

---

## 1. Qué hace la HU 5

Con las 6 respuestas del diagnóstico (HU 4), **una llamada estructurada a Gemini** genera el plan de la semana: una rutina por cada día de entrenamiento elegido, cada ejercicio con series, repeticiones o segundos de trabajo, descanso y una explicación de 2 a 4 pasos. El servidor valida el plan con reglas deterministas y lo guarda **completo o no lo guarda**. El plan es de **solo lectura**: no es un chat y no se puede editar; lo único posible es generar uno nuevo completo (regeneración, con límite semanal).

```
POST /api/v1/plan/generate   → 202 {plan_id, status:"generating"}   (S+P; exige X-Requested-With; la IA corre en segundo plano)
GET  /api/v1/plan/current    → 200 {status, days[5], …}             (S+P; NUNCA llama a la IA)
```

"S+P" significa sesión y perfil: ambas rutas usan `require_complete_profile` (401 sin sesión, 403 `ONBOARDING_REQUIRED` sin diagnóstico).

## 2. Arquitectura y archivos

```
apps/api/app/ai/                       # IA detrás de puertos (ADR-07); no depende de `profile` ni de `plan`
├── ports.py          # TextGenerator + TextRequest; AudioProcessor / VisionAnalyzer (solo contratos)
├── errors.py         # AIProviderError(kind), AIInvalidOutput, AIDisabled, AIBreakerOpen, AIFailure
├── registry.py       # PromptRegistry: prompts/<caso>/<versión>.yaml, valida claves y parámetros
├── privacy.py        # WeeklyPlanInput + PrivacyGuard (allowlist cerrada de 6 claves)
├── validators.py     # parse_json_output (tolera una cerca ```json)
├── resilience.py     # CircuitBreaker (con semiabierto) y tiempo/sleep inyectables
├── call_log.py       # modelo ai_call_logs + DbCallRecorder (sesión propia) / MemoryCallRecorder
├── gateway.py        # AIGateway.run(use_case, input) + get_ai_gateway()
├── adapters/
│   ├── gemini_text.py   # adaptador delgado sobre google-genai 2.29.0
│   └── fake_text.py     # FakeTextAdapter determinista + modo guion
└── use_cases/weekly_plan/
    ├── schema.py     # salida Pydantic estricta
    ├── rules.py      # reglas y estimador de duración (constantes en un solo lugar)
    └── use_case.py   # WEEKLY_PLAN: parsea + valida

apps/api/app/modules/plan/
├── calendar.py       # target_week, días restantes, estados por día (funciones puras)
├── models.py         # WeeklyPlan, PlanDay, PlanExercise + constantes de estados y fallos
├── repository.py     # PlanRepository
├── service.py        # PlanService.generate / current
├── runner.py         # puerto PlanJobScheduler (BackgroundTasks) + PlanGenerationJob
├── schemas.py
└── router.py         # solo POST /generate y GET /current

apps/api/prompts/weekly_plan/v1.yaml   # prompt versionado (fuera de app/)
apps/api/migrations/versions/0003_hu5_plan_schema.py
apps/api/scripts/smoke_gemini.py       # prueba manual con Gemini real (NO es parte del CI)
apps/api/tests/unit/…, tests/integration/test_plan_*.py, tests/golden/weekly_plan/*.json
```

Archivos **modificados** (cambios mínimos; HU 1–4 sin cambios de comportamiento):

| Archivo | Cambio |
|---|---|
| `core/config.py` | variables de IA, plan y rate limit; guardas de arranque (ver §3.1) |
| `core/db.py` | `get_session_factory()` para que la tarea abra sus propias sesiones |
| `core/clock.py` | `FrozenClock.set(fecha)` para pruebas de calendario |
| `app/ai/ports.py` | reemplaza el andamiaje previo (`TextGeneratorPort`, sin uso) por el contrato de esta HU |
| `profile/repository.py`, `profile/service.py` | `ProfileService.get_diagnostic(user_id)` (días ordenados) |
| `main.py` | incluye el router de plan y carga el prompt activo al arrancar (falla si no existe) |
| `migrations/env.py` | importa los modelos de plan y `ai_call_logs` |
| `requirements.txt` | `google-genai==2.29.0` (antes `>=2.25.0`); `pyyaml==6.0.3` ya estaba fijada |
| `.env.example` | variables nuevas |
| `tests/conftest.py` | el fixture `client` inyecta un gateway de prueba (adaptador falso + tiempo falso) y la fábrica de sesiones; teardown también vacía `ai_call_logs`; fixtures nuevas |
| `tests/fakes.py` | `FakeMonotonic`, `ManualScheduler` |
| `tests/unit/test_config.py` | pruebas de las guardas de arranque |

El `prompts/profile_summary/v1.yaml` del andamiaje inicial no se tocó; no lo usa ninguna HU todavía.

## 3. Cómo funciona

### 3.1 Configuración y guardas de arranque

| Variable | Defecto | Uso |
|---|---|---|
| `AI_ENABLED` | `true` | `false` → toda generación falla con `AI_UNAVAILABLE` sin llamar a nada |
| `AI_PROVIDER` | `fake` | `fake` (local y pruebas) o `gemini` |
| `GEMINI_API_KEY` | vacío | clave de Google AI Studio |
| `GEMINI_MODEL` | vacío | vacío = el modelo del YAML activo (`gemini-3.8-flash`) |
| `PROMPT_VERSION_WEEKLY_PLAN` | `v1` | versión activa del prompt |
| `AI_TIMEOUT_SECONDS` / `AI_TOTAL_BUDGET_SECONDS` / `AI_RETRY_MIN_REMAINING_SECONDS` | 20 / 40 / 5 | timeout por intento, presupuesto total y margen mínimo para reintentar |
| `AI_BREAKER_FAILURES` / `_WINDOW_SECONDS` / `_OPEN_SECONDS` | 5 / 60 / 30 | circuit breaker |
| `PLAN_MAX_GENERATIONS_PER_WEEK` | 3 | 1 inicial + 2 regeneraciones |
| `PLAN_STALE_SECONDS` | 90 | antigüedad a partir de la cual una generación se considera huérfana |
| `RATE_LIMIT_PLAN_GENERATE_PER_USER` / `_WINDOW_MINUTES` | 6 / 60 | rate limit de `POST /plan/generate` |

**La app no arranca** si:
- con `ENV=production` y `AI_ENABLED=true`, `AI_PROVIDER=fake` o `GEMINI_API_KEY` está vacía (mismo patrón que el mailer);
- `PLAN_STALE_SECONDS <= AI_TOTAL_BUDGET_SECONDS`, porque una generación viva se confundiría con una huérfana;
- el prompt activo no existe o le faltan claves.

### 3.2 Elección del modelo y verificación del SDK

- **SDK** `google-genai` **2.29.0**, la última versión publicada. Instala en Python 3.14 local y en `python:3.11-slim`.
- **API verificada en el código del SDK instalado**, no de memoria:
  - la llamada es `client.aio.models.generate_content(model, contents, config)`;
  - `GenerateContentConfig` acepta `system_instruction`, `response_mime_type`, `response_json_schema`, `temperature`, `max_output_tokens` y `thinking_config`;
  - `HttpOptions.timeout` va en **milisegundos**;
  - los errores son `errors.ClientError` (4xx, incluido 429), `errors.ServerError` (5xx), y `httpx.TimeoutException` / `httpx.ConnectError` para timeout y red;
  - sin `retry_options` el SDK **no reintenta**: los reintentos los controla solo el gateway.
- **Modelo:** se listaron con la clave los modelos Flash disponibles y se eligió **`gemini-3.8-flash`**, el Flash estable más reciente (sin *preview*), con 65 536 tokens de salida. Es configurable con `GEMINI_MODEL`, por ejemplo `gemini-3.5-flash`.
- **Hallazgos con el modelo real** (12-oct-2026):
  - `gemini-3.8-flash` **rechaza `minItems` / `maxItems`** en `response_json_schema` con un 400 genérico, por eso el esquema de salida no los incluye y las cantidades las imponen las reglas del servidor;
  - **rechaza `thinking_level=MINIMAL`**, así que se usa `LOW`;
  - a veces envuelve la respuesta en una cerca ```` ```json ````, que el parser tolera.

### 3.3 Módulo `ai`: gateway, privacidad, reintentos y breaker

`AIGateway.run(WEEKLY_PLAN, WeeklyPlanInput)`:

1. **`PrivacyGuard`**: construye la entrada desde una allowlist **cerrada** de exactamente 6 claves (`goal`, `term_weeks`, `fitness_level`, `session_minutes`, `training_days`, `has_machine_access`). Una clave de más o de menos es un error. `WeeklyPlanInput` vive en `ai`, así que `ai` no depende de `profile`.
2. **Prompt:** se renderiza desde el `PromptRegistry`. Los datos van como JSON entre `<<<DATOS` y `DATOS>>>`, y el prompt de sistema indica tratarlos como datos y nunca como instrucciones.
3. **IA deshabilitada** → `AIFailure(AI_UNAVAILABLE)` sin llamar a nada. 4. **Breaker abierto** → `AIFailure(AI_UNAVAILABLE)` sin llamar.
5. **Llamada** al `TextGenerator` con `asyncio.wait_for`; timeout por intento = `min(AI_TIMEOUT_SECONDS, presupuesto restante)`.
6. **Parseo y validación:** JSON (tolera una cerca de markdown que envuelva todo), esquema Pydantic estricto y reglas del caso de uso (§3.4).
7. **Métrica** en `ai_call_logs`, con una sesión **propia** para que persista aunque falle el guardado del plan. No guarda ni registra el prompt ni la respuesta.

**Reintentos**: como máximo 1, solo ante `timeout`, 5xx, 429, red o salida inválida (un `client_error` 4xx **no** se reintenta), y solo si después de una espera de 0,5 s quedan al menos `AI_RETRY_MIN_REMAINING_SECONDS` del presupuesto total. El tiempo es inyectable (`time_fn` y `sleep`).

**Circuit breaker** (en memoria, por proceso):
- **Apertura:** tras `AI_BREAKER_FAILURES` fallos de **disponibilidad** (timeout, 5xx, 429, red, 4xx) dentro de la ventana, se abre `AI_BREAKER_OPEN_SECONDS`.
- **Semiabierto:** pasado ese tiempo deja pasar **un** intento de prueba. Si responde, se cierra; si falla, se reabre.
- **Salida inválida:** **no** cuenta, porque es un problema de calidad y no de disponibilidad.

**Código de fallo final** (según el último intento):

| Último intento | Código |
|---|---|
| timeout | `GENERATION_TIMEOUT` |
| error del proveedor, breaker abierto o IA deshabilitada | `AI_UNAVAILABLE` |
| salida inválida | `AI_INVALID_OUTPUT` |

**`FakeTextAdapter`** (local y pruebas; nunca en producción, por las guardas de arranque):
- **Salida:** devuelve un plan **válido** y coherente con la entrada, dimensionado con el **mismo estimador** de `rules.py`.
- **Reservas de ejercicios:** 12 de peso corporal y 8 con máquina, cada uno con su explicación en español.
- **Ajuste:** adapta series, repeticiones y descanso al nivel y al objetivo, y respeta la regla de máquinas.
- **Modo guion** (`fake_ai.script(...)`): una cola de comportamientos por llamada. Hay `Valid`, `BrokenJson`, `Incoherent`, `Fail(kind)`, `Wait(event)` (espera controlada), `Callback` (por ejemplo, avanzar el reloj falso) y `Raw(texto)`.
- **Espía:** `fake_ai.requests` guarda todo lo que llegó al puerto.

### 3.4 Reglas del plan (`rules.py`, NFR-17 / NFR-18)

Cualquier violación → `AIInvalidOutput` → el plan completo se descarta.

- **Días:**
  - coinciden **exactamente** con `training_days` de la entrada, sin repetidos;
  - cada uno tiene de 3 a 8 ejercicios, con nombres únicos (sin distinguir mayúsculas ni tildes);
  - el título no puede estar vacío y tiene como máximo 60 caracteres.
- **Rangos:**
  - series 1–6, repeticiones 1–30, segundos de trabajo 10–120 y descanso 15–180;
  - **exactamente uno** entre `reps` y `work_seconds`;
  - para principiantes, series ≤ 4 y repeticiones ≤ 20.
- **Duración** (calculada por el servidor):
  - por ejercicio, `series × trabajo + (series − 1) × descanso`, donde el trabajo es `work_seconds` o `reps × 3 s`;
  - se suman 30 s de transición entre ejercicios y `estimated_minutes = ceil(s / 60)`;
  - debe ser ≤ `session_minutes`;
  - la cifra que da la IA **se ignora**; se guarda la calculada.
- **Sin acceso a máquinas** (plan solo de peso corporal):
  - ningún ejercicio con `requires_machine = true`;
  - ningún nombre, paso ni título con términos de equipamiento: prensa, polea, máquina, smith, jalón, contractora, elíptica, caminadora, trotadora, bicicleta estática, cables, mancuernas, barra olímpica, kettlebell…;
  - la comparación es sin tildes y por palabra completa.
- **Texto:**
  - ≥ 2 y ≤ 4 pasos por ejercicio, cada uno de hasta 200 caracteres;
  - sin URLs, sin HTML y sin términos de dieta o consejo médico (dieta, nutrición, suplemento, calorías, proteína, medicamento, diagnóstico, esteroides…);
  - una heurística de idioma **por ejercicio** rechaza los que tienen ≥ 3 palabras vacías del inglés y más palabras en inglés que en español.
- **Tipado estricto:** un `bool` no es un entero, no se aceptan números como texto ni flotantes, y las claves desconocidas se ignoran (nunca se guardan).

### 3.5 Módulo `plan`

**Calendario** (`calendar.py`, con el `Clock` en America/Bogota):
- **`target_week(hoy)`:** de lunes a viernes devuelve la semana actual con `start_date = hoy`; el sábado o el domingo, el lunes siguiente en ambos campos.
- **Estado de cada día:**
  - `training`: hay fila en `plan_days`;
  - `rest`: la fecha es ≥ `start_date` y no hay fila;
  - `unplanned`: la fecha es anterior a `start_date`.
  - `completed` no se emite todavía (Épicas 4–5).

**Entrada a la IA**: `training_days` filtrado a las fechas ≥ `start_date`. Por ejemplo, un miércoles con días `[1,3,5]` envía `[3,5]`. El `profile_snapshot` guarda las 6 respuestas **completas**, sin filtrar. **Plan vacío**: si no queda ningún día (por ejemplo, un viernes con días `[1,2]`), no se llama a la IA: el plan queda `ready` sin días y con `prompt_version` nulo.

**`POST /plan/generate`**, en este orden:
1. `require_complete_profile`. El `user_id` sale de la sesión y el cuerpo se ignora.
2. Marca como `STALE` las generaciones huérfanas del usuario (antigüedad ≥ `PLAN_STALE_SECONDS`, con un UPDATE condicionado).
3. **Idempotencia**: si hay una generación en curso, responde 202 con **el mismo `plan_id`**. No programa nada, no llama a la IA y no consume rate limit.
4. Calcula la semana y busca el plan `ready` de esa semana:
   - **sin plan:** `generation_number = 1`;
   - **con plan y diagnóstico igual:** 409 `PLAN_UP_TO_DATE`;
   - **con plan, diagnóstico distinto y `generation_number ≥ PLAN_MAX_GENERATIONS_PER_WEEK`:** 429 `REGENERATION_LIMIT`, con `Retry-After` hasta el lunes siguiente;
   - **con plan, diagnóstico distinto y dentro del límite:** `generation_number = anterior + 1`.

   Los intentos fallidos no consumen el límite semanal.
5. **Rate limit** por usuario → 429 `RATE_LIMITED` con `Retry-After`. Los pasos 3 y 4 (idempotencia, 409 y 429 de límite) **no** consumen cupo.
6. Borra las filas `failed` del usuario, inserta la fila `generating` (snapshot, `generation_number`, `created_at` del `Clock`) y hace commit.
   - **Carrera:** el índice único parcial `uq_weekly_plans_generating` lanza `IntegrityError`, que se captura para responder 202 con el `plan_id` ganador. Nunca hay un 500 ni dos generaciones.
7. Programa la tarea con el puerto `PlanJobScheduler` y responde **202**.

**La tarea** (`PlanGenerationJob`, en `BackgroundTasks`, después de responder):
1. **Lectura:** lee la fila en una sesión corta y la **cierra**. Si la fila ya no existe o no está `generating` (cuenta eliminada o `STALE`), termina en silencio.
2. **Llamada:** llama al gateway **sin ninguna conexión ni transacción abierta**. Una prueba lo verifica con `pg_stat_activity`.
3. **Guardado en UNA transacción corta:**
   - (a) borra el `ready` anterior de la semana, si es una regeneración (el cascade borra sus días y ejercicios);
   - (b) `UPDATE … SET status='ready' WHERE id=:id AND status='generating'`; si no afecta filas, hace **rollback y termina en silencio**;
   - (c) inserta días y ejercicios, con los minutos calculados por el servidor;
   - (d) borra las filas `failed` del usuario.

   El orden (a), (b), (c) evita violar el índice único de `ready` y no deja filas huérfanas si la cuenta se borró.
4. **`AIFailure`:** la fila pasa a `failed` con su código (UPDATE condicionado) y no se guardan días ni ejercicios.
5. **Error interno inesperado** (por ejemplo, de BD al guardar): la fila pasa a `failed` `AI_UNAVAILABLE` y la excepción se registra sin datos personales. **Nunca queda en `generating`.**

**`GET /plan/current`** (marca `STALE` y no llama nunca a la IA):
```json
{ "status": "none|generating|ready|failed", "regenerating": false, "week_start": "2026-10-12",
  "start_date": "2026-10-12", "generation_number": 1, "outdated": false, "can_regenerate": false,
  "failure": null,
  "days": [{"date": "2026-10-12", "weekday": 1, "status": "training", "title": "…", "estimated_minutes": 25}, …] }
```
- **`status`:** `ready` si hay plan; si no, `generating` si hay una generación en curso; si no, `failed` si hay una fila fallida; si no, `none`.
- **`regenerating`:** hay plan y además una generación en curso.
- **`failure`:** se informa siempre que exista una fila fallida, incluso si hay un plan `ready` anterior. Una regeneración fallida **no** reemplaza el plan vigente.
- **`outdated`:** el snapshot del plan es distinto del diagnóstico actual.
- **`can_regenerate`:** `outdated` y dentro del límite semanal y sin una generación en curso.
- **`days`:** siempre los 5 días de lunes a viernes. Sin plan, los 5 salen como `unplanned`; `title` y `estimated_minutes` son `null` cuando no hay rutina.
- **Lo que no se expone todavía:** los ejercicios y sus explicaciones; llegan con las HU 10, 12 y 13.

**Inmutabilidad (AC-5-9 / NFR-22)**: el router solo declara `POST /generate` y `GET /current`. `PUT`, `PATCH` y `DELETE` responden 405, y cualquier otra ruta de plan, 404.

### 3.6 Modelo de datos (migración `0003_hu5_plan_schema`)

| Tabla | Clave / FK | Restricciones |
|---|---|---|
| `weekly_plans` | `id` PK; `user_id → users ON DELETE CASCADE` | `ck_weekly_plans_status`, `_week_start_monday` (isodow = 1), `_start_date` (entre `week_start` y `+4`), `_generation_number` (≥ 1), `_failure_iff_failed`, `_failure_code` (4 códigos), `_ready_iff_ready_at`; índices `ix_weekly_plans_user_week`, **`uq_weekly_plans_ready`** (`user_id, week_start` WHERE `ready`), **`uq_weekly_plans_generating`** (`user_id` WHERE `generating`) |
| `plan_days` | PK `(plan_id, plan_date)`; `plan_id → weekly_plans CASCADE` | `ck_plan_days_weekday` (isodow 1–5), `_title` (1–60), `_estimated_minutes` (1–60) |
| `plan_exercises` | `id` PK; FK compuesta `(plan_id, plan_date) → plan_days CASCADE` | `uq_plan_exercises_position`; CHECK de `sets` 1–6, `reps` 1–30, `work_seconds` 10–120, `rest_seconds` 15–180, `num_nonnulls(reps, work_seconds) = 1`, `steps` arreglo JSON de 2 a 4 |
| `ai_call_logs` | `id` PK | **sin `user_id` y sin contenido**; `ck_ai_call_logs_status` (`ok`, `invalid_output`, `timeout`, `provider_error`, `breaker_open`, `disabled`) |

- **Valores literales:** la migración escribe los valores literalmente y un test anti-deriva los compara con las constantes del código (`PLAN_STATUSES`, `FAILURE_CODES`, `CALL_STATUSES` y los rangos de `rules.py`).
- **Cascada:** los tests de la HU 3 pasan **sin cambios** y `CASCADE_EXCEPTIONS` sigue vacío.
- **Métricas tras eliminar una cuenta:** las filas de `ai_call_logs` se conservan, porque no contienen ningún dato del usuario.

### 3.7 Logs

Eventos `plan_generation_started`, `plan_generated` y `plan_generation_failed`, con `plan_id`, `generation_number`, `failure_code`, intentos y latencia. **Nunca** incluyen el prompt, la respuesta, el contenido del plan, el correo ni el apodo; una prueba lo verifica.

## 4. Cómo se hicieron las pruebas

Mismo enfoque que HU 1–4: pytest + `httpx.AsyncClient` (`ASGITransport`) contra **Postgres real** con las migraciones de Alembic. **Ninguna prueba llama a Gemini.**

**Fixtures nuevas** (`tests/conftest.py`):
- **IA de prueba:**
  - `fake_ai`: `FakeTextAdapter` con su cola de comportamientos; `fake_ai.requests` es el espía del puerto;
  - `ai_time`: `FakeMonotonic`, el reloj falso del gateway;
  - `ai_gateway`: gateway real con adaptador falso, breaker sobre el tiempo falso y métricas en BD. El fixture `client` lo inyecta siempre.
- **Planificador:** `manual_scheduler` guarda las tareas y las ejecuta con `run_next()` / `run_all()`. Con `ASGITransport`, los `BackgroundTasks` terminarían antes de que el POST devuelva, y no se podría observar `generating`.
- **Datos y llamadas:**
  - `student_with_profile`: estudiante con perfil y sesión;
  - `plan_api.generate/current`: hacen las llamadas;
  - `plan_footprint`: cuenta planes, días y ejercicios del usuario.

**Técnicas destacadas**:
- **Bug real encontrado por las pruebas:** el planificador real programaba `lambda: job.run(id)`. Starlette decide con `is_async_callable()` si espera la tarea; con una lambda la mandaba a un threadpool, **la corrutina nunca se ejecutaba y la generación no ocurría**. Lo destapó la prueba que usa `BackgroundTasks` reales (el `ManualScheduler` lo ocultaba porque hace `await`). Corregido con un envoltorio `async def`.
- **Respuesta antes que la IA:** con la técnica del middleware ASGI de la HU 1, se comprueba que la llamada a la IA ocurre **después** de enviar la respuesta. Con la IA tardando 1,5 s, el POST respondió en **57 ms**.
- **Sin transacciones abiertas:** mientras la tarea espera a la IA (`Wait` con `asyncio.Event`), `pg_stat_activity` no muestra conexiones `idle in transaction`.
- **Tiempo falso:** con `FakeMonotonic` se prueban el presupuesto (sin reintento si quedan < 5 s), el timeout del segundo intento (el presupuesto restante) y el breaker (apertura, intento de prueba y reapertura).
- **`STALE`:** con `FrozenClock`, a 89 s la generación sigue `generating` y a 91 s pasa a `failed STALE`. Después, una finalización tardía de la tarea original no escribe nada.
- **Privacidad en dos fronteras:** con una cuenta de valores reconocibles se serializa todo lo que recibe (a) el puerto `TextGenerator` y (b) el cliente del SDK, usando el **adaptador Gemini real** con un cliente falso. No aparecen el apodo, el correo, la contraseña, el programa (código y nombre), el `user_id`, el `plan_id` ni el token de sesión, y las claves enviadas son exactamente las 6 de la allowlist.
- **Anti-deriva:**
  - YAML ↔ Pydantic: las claves del esquema de entrada y de salida coinciden;
  - código ↔ CHECK: los estados, los códigos y los límites de rango;
  - las **480 combinaciones** (4 objetivos × 3 niveles × 4 duraciones × 2 accesos × 5 conjuntos de días) generadas por el adaptador falso pasan las reglas.
- **Golden** (`tests/golden/weekly_plan/`): principiante sin máquinas, avanzado con máquinas, un solo día y cinco días, con las propiedades esperadas.
- **Mutaciones manuales:**
  - **Breaker:** un breaker semiabierto que no se resolvía cuando el adaptador lanzaba `AIInvalidOutput` quedaba bloqueado para siempre; se corrigió.
  - **Idempotencia:** al quitar la comprobación explícita, el índice único sigue evitando la duplicación, pero el rate limit se consume, y lo detecta `test_rate_limit_por_usuario`.
- **Tiempos medidos:**
  - `POST /plan/generate`: 50 ms (NFR-06, ≤ 2 s);
  - `GET /plan/current`: 41 ms (NFR-05, ≤ 2 s);
  - con **Gemini real**, plan listo en 6–17 s (8–9 s en el recorrido por la API), por debajo de los 30 s de NFR-06.

**Resultados**: 504 pruebas (296 de HU 1–4 sin cambios + 208 nuevas) pasan en Python 3.14 local y en `python:3.11-slim` (Docker). Hay un `DeprecationWarning` del propio SDK en Python 3.14 (`_UnionGenericAlias`), ajeno al código de FITIA.

### Tabla AC → pruebas

| AC | Prueba(s) |
|---|---|
| AC-5-1 | `test_ac_5_1_generar_muestra_la_semana_con_la_rutina_de_cada_dia`, `test_status_none_antes_de_generar` |
| AC-5-2 | `test_ac_5_2_solo_los_dias_elegidos_tienen_rutina` (lunes, miércoles, sábado, domingo), `test_ac_5_2_viernes_sin_dias_restantes_da_plan_vacio_sin_llamar_a_la_ia`, unitarias de `test_plan_calendar.py` |
| AC-5-3 | `test_ac_5_3_ninguna_sesion_supera_el_tiempo_ni_usa_maquinas_sin_acceso` (4 duraciones × 2 accesos), reglas de duración y máquinas en `test_weekly_plan_rules.py` |
| AC-5-4 | `test_ac_5_4_cada_ejercicio_trae_series_repeticiones_descanso_y_explicacion` |
| AC-5-5 | `test_ac_5_5_el_puerto_text_generator_solo_recibe_la_allowlist`, `test_ac_5_5_el_cliente_de_gemini_solo_recibe_la_allowlist`, `test_privacy_guard_solo_deja_pasar_la_allowlist` |
| AC-5-6 | `test_ac_5_6_si_la_ia_falla_no_se_guarda_nada_y_se_puede_reintentar` (timeout, 5xx, 429, 4xx, JSON roto, incoherente), `…_ia_deshabilitada_falla_sin_llamar`, `…_breaker_abierto_falla_sin_llamar`, `…_error_al_guardar_el_cuarto_ejercicio_revierte_todo`, `…_una_regeneracion_fallida_no_reemplaza_el_plan_vigente`, unitarias de `test_ai_gateway.py` |
| AC-5-7 | `test_ac_5_7_dos_post_seguidos_devuelven_la_misma_generacion`, `…_dos_post_simultaneos_crean_una_sola_generacion`, `…_con_plan_vigente_y_diagnostico_igual_responde_409`, `test_indices_unicos_parciales` |
| AC-5-8 | `test_ac_5_8_mientras_se_genera_el_usuario_no_queda_bloqueado`, `…_la_llamada_a_la_ia_ocurre_despues_de_responder_aunque_sea_lenta`, `…_durante_la_espera_a_la_ia_no_hay_transacciones_abiertas`, `test_stale_*` |
| AC-5-9 | `test_ac_5_9_la_api_no_ofrece_ninguna_operacion_para_modificar_el_plan` |
| Regeneración | `test_regeneracion_reemplaza_el_plan_anterior`, `test_regeneracion_tiene_limite_semanal`, `test_un_intento_fallido_no_consume_el_limite_semanal` |
| NFR-05 / 06 / 16 | `test_nfr_16_consultar_el_plan_nunca_llama_a_la_ia`, `test_nfr_06_post_generate_responde_rapido` |
| NFR-10 | `test_nfr_10_un_usuario_no_ve_ni_toca_el_plan_de_otro` |
| NFR-11 | `test_nfr_11_respuestas_del_plan_llevan_no_store`, `test_nfr_11_errores_409_y_403_tambien_llevan_no_store` |
| NFR-12 | `test_nfr_12_eliminar_la_cuenta_borra_plan_dias_y_ejercicios`, `…_con_la_generacion_pendiente_termina_en_silencio`, `test_cascada_hacia_users_en_tablas_del_plan` + cascada de la HU 3 |
| NFR-14 / 15 / 17 / 18 / 22 / 23 | privacidad, fallos, reglas, inmutabilidad e índices (filas anteriores) |
| Esquema | `test_plan_schema.py` (CHECK, índices, `ai_call_logs`, anti-deriva) |
| Rate limit | `test_rate_limit_por_usuario`, `test_los_409_no_consumen_cupo` |
| Seguridad | `test_sin_sesion_devuelve_401`, `test_sin_perfil_devuelve_403_onboarding_required`, `test_sin_encabezado_csrf_devuelve_403` |
| Logs | `test_logs_sin_correo_apodo_prompt_respuesta_ni_contenido_del_plan`, `test_logs_de_una_generacion_fallida` |
| Unitarias | `test_plan_calendar.py`, `test_weekly_plan_rules.py` (34 violaciones), `test_fake_text_adapter.py` (480 combinaciones), `test_ai_privacy_registry.py`, `test_ai_gateway.py`, `test_gemini_adapter.py`, `test_config.py` |
| Golden | `tests/golden/test_weekly_plan_golden.py` |

## 5. Cómo probarlo manualmente

### 5.1 En local con la IA falsa (sin clave)

```bash
POSTGRES_PORT=5433 docker compose up -d db
cd apps/api
.venv/bin/alembic upgrade head          # aplica 0003_hu5_plan_schema
# .env: AI_PROVIDER=fake, COOKIE_SECURE=false, MAIL_PROVIDER=console
.venv/bin/uvicorn app.main:app --reload --proxy-headers
```

### 5.2 En local con Gemini real

```bash
# .env (NUNCA lo subas al repositorio; .env ya está en .gitignore):
#   AI_PROVIDER=gemini
#   GEMINI_API_KEY=<tu clave>
#   GEMINI_MODEL=            # vacío = gemini-3.8-flash
.venv/bin/uvicorn app.main:app --reload --proxy-headers
```

**Script de humo** (no toca la BD ni forma parte del CI): genera con el gateway de producción y valida con las reglas.
```bash
GEMINI_API_KEY=<tu clave> .venv/bin/python -m scripts.smoke_gemini                 # 3 casos
GEMINI_API_KEY=<tu clave> .venv/bin/python -m scripts.smoke_gemini --case beginner
GEMINI_API_KEY=<tu clave> GEMINI_MODEL=gemini-3.5-flash .venv/bin/python -m scripts.smoke_gemini
```
Imprime cada día con sus ejercicios, intentos y latencia, y termina con código distinto de 0 si algún caso falla.

### 5.3 Recorrido con curl

```bash
B=http://localhost:8000/api/v1
H=(-H "X-Requested-With: fitia" -H "Content-Type: application/json")
JAR=/tmp/fitia-cookies.txt; rm -f $JAR

# 1. Registro, verificación (token del correo impreso por uvicorn), login y diagnóstico
curl -s "${H[@]}" $B/auth/register -d '{"nickname":"Pantera","email":"ana.gomez@correounivalle.edu.co",
  "password":"contrasena-segura","program_code":"ING-SIS","accepted_terms":true}'
curl -s "${H[@]}" $B/auth/verify-email -d '{"token":"PEGA_EL_TOKEN"}'
curl -s -c $JAR "${H[@]}" $B/auth/login -d '{"email":"ana.gomez@correounivalle.edu.co","password":"contrasena-segura"}'
curl -s -b $JAR "${H[@]}" $B/onboarding/complete -d '{"goal":"strength","term_weeks":8,"fitness_level":"beginner",
  "session_minutes":30,"training_days":[1,3,5],"has_machine_access":false}'

# 2. Estado inicial → status "none", 5 días "unplanned"
curl -s -b $JAR $B/plan/current

# 3. Generar → 202 {"plan_id": "...", "status": "generating"}
curl -s -b $JAR "${H[@]}" -X POST $B/plan/generate

# 4. Consultar mientras se genera (status "generating"), y luego cada ~3 s hasta "ready"
curl -s -b $JAR $B/plan/current

# 5. Segundo POST con el plan vigente → 409 PLAN_UP_TO_DATE
curl -s -b $JAR "${H[@]}" -X POST $B/plan/generate

# 6. Simular un cambio de perfil (el PATCH llega con la HU 6) → outdated:true, can_regenerate:true
docker exec fitia_postgres psql -U postgres -d fitia_db -c "UPDATE profiles SET session_minutes = 15"
curl -s -b $JAR $B/plan/current

# 7. Regenerar → 202; al terminar: generation_number 2 y un solo plan "ready"
curl -s -b $JAR "${H[@]}" -X POST $B/plan/generate

# 8. Fallo simulado: reinicia uvicorn con AI_ENABLED=false, cambia el perfil otra vez y genera
docker exec fitia_postgres psql -U postgres -d fitia_db -c "UPDATE profiles SET goal = 'endurance'"
curl -s -b $JAR "${H[@]}" -X POST $B/plan/generate
curl -s -b $JAR $B/plan/current      # status "ready" (el plan anterior sigue) + failure {"code":"AI_UNAVAILABLE"}

# 9. Reintento: reinicia uvicorn con AI_ENABLED=true y vuelve a generar → generation_number 3
curl -s -b $JAR "${H[@]}" -X POST $B/plan/generate

# 10. Límite semanal: cambia el perfil y genera → 429 REGENERATION_LIMIT con Retry-After
# 11. Inmutabilidad: PUT, PATCH y DELETE sobre /plan/current o /plan/generate → 405
# 12. Eliminar la cuenta → 204 (y comprobar con psql, §5.5)
curl -s -b $JAR "${H[@]}" $B/me/delete-account -d '{"confirm":true}'
```

Resultado de este recorrido con Gemini real (12-oct-2026, lunes):
- **Generación:** POST en 13 ms; plan listo en unos 12 s de sondeo (8,2 s de IA), con lunes, miércoles y viernes de entrenamiento y martes y jueves de descanso.
- **409** al repetir el POST con el plan vigente.
- **Regeneración:** generación 2 en unos 12 s.
- **Fallo simulado:** `failure AI_UNAVAILABLE` con el plan anterior todavía visible.
- **Reintento:** generación 3 en unos 10 s.
- **Límite semanal:** 429 con `Retry-After: 545047`.
- **Solo lectura:** 405 en `PUT`, `PATCH` y `DELETE`.
- **Eliminación:** 0 filas de usuario, perfil, planes, días y ejercicios.

### 5.4 Simular `STALE` y un plan desactualizado con SQL

```sql
-- Generación huérfana (p. ej. Render reinició la instancia): retrocede su fecha de creación
UPDATE weekly_plans SET created_at = now() - interval '2 minutes' WHERE status = 'generating';
-- El siguiente GET /plan/current (o POST /plan/generate) la marca failed / STALE.

-- Plan desactualizado: cualquier cambio en el perfil o en los días
UPDATE profiles SET goal = 'endurance';
DELETE FROM profile_training_days WHERE weekday = 5;
-- GET /plan/current → outdated:true y can_regenerate:true (si no se superó el límite)
```

### 5.5 Revisar la BD con psql

```bash
docker exec -it fitia_postgres psql -U postgres -d fitia_db
```
```sql
SELECT status, generation_number, prompt_version, failure_code, week_start, start_date FROM weekly_plans;
SELECT plan_date, title, estimated_minutes FROM plan_days ORDER BY plan_date;
SELECT plan_date, position, name, sets, reps, work_seconds, rest_seconds, requires_machine, steps
FROM plan_exercises ORDER BY plan_date, position;
SELECT status, model, attempts, latency_ms, created_at FROM ai_call_logs ORDER BY created_at;  -- sin user_id

-- Después de eliminar la cuenta: todo en 0 (las métricas de ai_call_logs se conservan; no tienen datos del usuario)
SELECT (SELECT count(*) FROM users) users, (SELECT count(*) FROM weekly_plans) planes,
       (SELECT count(*) FROM plan_days) dias, (SELECT count(*) FROM plan_exercises) ejercicios;
```

### 5.6 Pruebas automáticas

```bash
cd apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/fitia_test .venv/bin/pytest -v
# Solo la HU 5:
TEST_DATABASE_URL=... .venv/bin/pytest -v tests/integration/test_plan_*.py tests/golden \
  tests/unit/test_plan_calendar.py tests/unit/test_weekly_plan_rules.py tests/unit/test_fake_text_adapter.py \
  tests/unit/test_ai_privacy_registry.py tests/unit/test_ai_gateway.py tests/unit/test_gemini_adapter.py
# Tiempos de NFR-05/06:
TEST_DATABASE_URL=... .venv/bin/pytest -s -k "nfr_06 or nfr_16 or despues_de_responder"
```
No ejecutes dos corridas de pytest en paralelo contra la misma `TEST_DATABASE_URL` (ver HU4.md §4).

## 6. Qué debe hacer la SPA

- **`status: "none"`:** llamar a `POST /plan/generate`, típicamente justo después del 201 del diagnóstico.
- **`status: "failed"`:** **no** llamar al POST automáticamente; mostrar el aviso con el botón **"Reintentar"**, que es el que hace el POST.
- **`status: "generating"` o `regenerating: true`:**
  - consultar `GET /plan/current` cada **~3 s** sin bloquear la navegación (el resto de la app sigue usable);
  - pasados **~60 s**, mostrar un aviso con las opciones "seguir esperando" o "reintentar". La generación huérfana se resuelve sola como `STALE` a los 90 s.
- **`ready` con `failure` informado:** mostrar el plan vigente y un aviso de que la regeneración falló, con "Reintentar".
- **`outdated: true`:** ofrecer "Actualizar mi plan" solo si `can_regenerate` es `true`.
- **409 `PLAN_UP_TO_DATE`:** tratarlo como "ya tienes plan" y mostrar `GET /plan/current`.
- **429** (`RATE_LIMITED` o `REGENERATION_LIMIT`): mostrar el mensaje y el tiempo de `Retry-After`.
- **Sin edición:** **no** ofrecer ninguna acción de edición del plan; la API no la tiene.

## 7. Supuestos tomados

1. **Tiempos objetivo (NFR-06):** el plan debe quedar listo en ≤ 30 s en el 95 % de los casos. Con Gemini real se midieron 6–17 s en el primer intento, y el peor caso con un reintento queda acotado a 40 s (`AI_TOTAL_BUDGET_SECONDS`).
2. **Ejercicios por día:** de 3 a 8.
3. **Principiantes:** como máximo 4 series y 20 repeticiones.
4. **Sin acceso a máquinas el plan es solo de peso corporal:** tampoco mancuernas, barras olímpicas ni kettlebells (están en `MACHINE_TERMS`, configurable).
5. **La salida inválida no cuenta para el breaker:** es un problema de calidad, no de disponibilidad.
6. **Plan vacío:** si no quedan días de entrenamiento esta semana, el plan queda `ready` sin días y sin llamar a la IA.
7. **Error interno inesperado al guardar:** `failed` con `AI_UNAVAILABLE`.
8. **`reps` y `work_seconds` en la BD:** el CHECK exige **exactamente uno** (`num_nonnulls = 1`), más estricto que "al menos uno" y coherente con las reglas.
9. **`GEMINI_MODEL` vacío:** se usa el modelo declarado en el YAML del prompt activo (`gemini-3.8-flash`); si se define, lo sobrescribe.
10. **Esquema de salida sin `minItems` / `maxItems`:** el modelo los rechaza; las reglas del servidor imponen las cantidades.
11. **`thinking_level: LOW`**, porque `MINIMAL` no está soportado en `gemini-3.8-flash`.
12. **Heurística de idioma por ejercicio:** se rechaza con ≥ 3 palabras vacías del inglés y más en inglés que en español. Nombres como "Bird-Dog" entre paréntesis pasan.
13. **Espera antes del reintento:** 0,5 s fijos (`RETRY_BACKOFF_SECONDS`), contados dentro del presupuesto.
14. **`REGENERATION_LIMIT`** incluye `Retry-After` hasta el lunes siguiente, a las 00:00 de Bogotá.
15. **`title` y `estimated_minutes`** se devuelven como `null`, no se omiten, en los días sin rutina.
16. **El breaker y el rate limit viven en memoria, por proceso:** con varias instancias en Render, cada una tiene los suyos.
17. **`ai_call_logs` se conserva al eliminar una cuenta:** no contiene ningún dato del usuario.

## 8. Pendiente / fuera de alcance

- **HU 6:** `PATCH /profile`. Al cambiar el perfil, el plan queda `outdated` y se regenera con este mismo flujo.
- **HU 10, 12 y 13:** `GET /plan/today`, `/plan/days/{date}` y `/plan/exercises/{id}/guide`, que expondrán los ejercicios y sus explicaciones. El aviso orientativo lo pondrá la API (HU 13), no la IA.
- **Operación:**
  - definir en Render `AI_PROVIDER=gemini` y `GEMINI_API_KEY` (sin ellas, la app no arranca en producción);
  - vigilar `ai_call_logs`: tasa de `invalid_output` y latencias;
  - para cambiar el prompt, crear `v2.yaml` y subir `PROMPT_VERSION_WEEKLY_PLAN`; nunca editar `v1`.
- **Fuera de alcance:** generación automática por cron, plan de respaldo estático, chat, adaptación por progreso, puntos, retos y ranking.
