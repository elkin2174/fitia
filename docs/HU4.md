# HU 4 — Diagnóstico inicial predefinido

Documentación de la implementación backend de la HU 4 del MVP FITIA: qué se construyó, cómo funciona, cómo se probó y cómo probarlo a mano. Se apoya en [H1.md](H1.md), [HU2.md](HU2.md) y [HU3.md](HU3.md).

> Estado: implementado y probado. 296 pruebas pasando (192 de HU 1–3 + 104 nuevas) en Python 3.14 local y 3.11 en Docker. Sin commit todavía. Nueva migración `0002_hu4_profile_schema` (con `downgrade`, probado arriba-abajo-arriba).

---

## 1. Qué hace la HU 4

El estudiante responde **una sola vez** un diagnóstico **predefinido** de 6 preguntas cerradas. No hay IA en esta HU. Al confirmarlo se guarda su perfil y la SPA pasa a la generación del plan (HU 5, no implementada aquí). Desde ese momento el login lo lleva a la pantalla principal (`next: "home"`).

```
GET  /api/v1/onboarding/questionnaire   → 200 {questions:[…]}   (requiere sesión; no exige diagnóstico)
POST /api/v1/onboarding/complete        → 201 {profile:{…}}     (requiere sesión + X-Requested-With)
```

| Pregunta (`id`) | Tipo | `code` aceptados (tipo JSON) |
|---|---|---|
| `goal` | single | `"general_health"`, `"strength"`, `"endurance"`, `"weight_loss"` |
| `term_weeks` | single | `4`, `8`, `12` (enteros) |
| `fitness_level` | single | `"beginner"`, `"intermediate"`, `"advanced"` |
| `session_minutes` | single | `15`, `30`, `45`, `60` (enteros) |
| `has_machine_access` | single | `true`, `false` (booleanos) |
| `training_days` | multi | `1`..`5` (enteros; lunes a viernes; uno o más) |

## 2. Arquitectura y archivos

Dos módulos con responsabilidades separadas. No hay imports cruzados de repositorios (ADR-01): `onboarding` solo usa `ProfileService`, nunca `ProfileRepository`.

```
apps/api/app/modules/profile/          # dueño de los datos del perfil y de las listas cerradas
├── options.py        # ÚNICA fuente de los valores permitidos
├── models.py         # Profile, ProfileTrainingDay (CHECK construidos desde options.py)
├── schemas.py        # DiagnosticProfile: DTO con exactamente los 6 campos (base de la allowlist de la HU 5)
├── validators.py     # validate_diagnostic(raw, partial=False) + validation_message(errors)
├── repository.py     # ProfileRepository (exists, add_profile, add_training_days)
└── service.py        # ProfileService: create_from_diagnostic, has_profile

apps/api/app/modules/onboarding/
├── questionnaire.py  # textos y etiquetas en español, construidos sobre profile/options.py
├── schemas.py        # QuestionnaireResponse, CompleteDiagnosticResponse
├── service.py        # OnboardingService: valida y delega en ProfileService
├── router.py         # GET /questionnaire, POST /complete
└── status.py         # puerto OnboardingStatus + ProfileOnboardingStatus (reemplaza el provisional)

apps/api/migrations/versions/0002_hu4_profile_schema.py
apps/api/tests/unit/test_profile_validators.py
apps/api/tests/integration/test_onboarding_questionnaire.py
apps/api/tests/integration/test_onboarding_complete.py
apps/api/tests/integration/test_profile_schema.py
```

Archivos **modificados**:

| Archivo | Cambio |
|---|---|
| `onboarding/status.py` | `ProfileOnboardingStatus` (consulta `ProfileService.has_profile`) reemplaza a `PendingOnboardingStatus`, que se **eliminó**: ningún test la usaba y los tests que necesitan un valor fijo usan `FakeOnboardingStatus`. `get_onboarding_status()` ahora depende de la sesión de BD y del reloj |
| `main.py` | incluye el router de onboarding |
| `migrations/env.py` | importa los modelos de perfil (para `Base.metadata`) |
| `tests/conftest.py` | `VALID_DIAGNOSTIC`, fixtures `student`, `make_student`, `complete_diagnostic`; la fixture `protected_route` se movió aquí desde `test_session_guards.py` para reutilizarla |
| `tests/integration/test_delete_account.py` | 2 aserciones de huella (ver §6) |
| `tests/integration/test_login.py` | solo un comentario que mencionaba `PendingOnboardingStatus` |

`login`, `GET /me`, `require_complete_profile`, logout y eliminación de cuenta **no cambiaron**: el efecto llega solo por el puerto `OnboardingStatus`.

## 3. Cómo funciona

### 3.1 Fuente única de verdad: `profile/options.py`

Las tuplas `GOALS`, `TERM_WEEKS`, `FITNESS_LEVELS`, `SESSION_MINUTES`, `MACHINE_ACCESS` y `WEEKDAYS` alimentan:
- el **cuestionario**: si se agrega un valor sin etiqueta, la app falla al importar (`KeyError`), así que la deriva se nota de inmediato;
- el **validador**;
- los **CHECK de los modelos** SQLAlchemy;
- los **`Literal`/`enum` del OpenAPI** del DTO, útiles para el cliente generado (ADR-13);
- los **tests**.

La migración `0002` escribe esos valores **literales** a propósito: una migración es historia inmutable y no debe importar código de la app. El test anti-deriva (§4) verifica que la BD acepte cada valor de `options.py` y rechace los de fuera.

### 3.2 Cuestionario (`GET /onboarding/questionnaire`)

Requiere sesión (`get_current_user`), pero **no** el diagnóstico. Sigue respondiendo después de completarlo, porque la HU 6 reutilizará las opciones. Devuelve las 6 preguntas en orden, cada una con `id`, `text` (en español), `type` (`single`/`multi`) y `options: [{code, label}]`. Los `code` conservan su tipo JSON (`true`, `4`, `"strength"`): el esquema usa `StrictBool | StrictInt | StrictStr` para que `true` no se serialice como `1`. Lleva `no-store` por el middleware.

### 3.3 Completar el diagnóstico (`POST /onboarding/complete`)

1. **Guard** `get_current_user` (no `require_complete_profile`). El `user_id` sale de la sesión. Cualquier campo extra (`user_id`, `weight_kg`, `nickname`…) **se ignora y no se guarda** (NFR-10).
2. **Cuerpo**: se acepta cualquier JSON (`Body(default=None)` de tipo `Any`). Si no es un objeto (`null`, lista, texto o cuerpo vacío) se trata como `{}`, así el resultado es la lista completa de campos faltantes. Un JSON malformado sigue el 422 estándar (`INVALID_JSON`).
3. **Validación cerrada** (`profile/validators.py`). Acumula **todos** los errores, en el orden de las preguntas, y no guarda nada hasta que todo es válido:

   | Campo | Ausente / `null` | Inválido |
   |---|---|---|
   | `goal`, `fitness_level` | `REQUIRED` | no es `str` o no está en la lista → `INVALID_OPTION` (comparación exacta: sin trim ni minúsculas) |
   | `term_weeks`, `session_minutes` | `REQUIRED` | no es `int` estricto (`true`, `4.0` y `"4"` se rechazan) o no está en la lista → `INVALID_OPTION` |
   | `has_machine_access` | `MACHINE_ACCESS_REQUIRED` (sin valor por defecto) | no es `bool` JSON (`"si"`, `1`, `"true"`) → `INVALID_OPTION` |
   | `training_days` | `DAYS_REQUIRED` (también con `[]`) | no es lista, o algún elemento no es `int` estricto entre 1 y 5 (`[true]`, `[1,"2"]`, `[6]`) → `INVALID_OPTION` |

   El tipado es estricto porque en Python `bool` es subclase de `int`: `type(v) is int` evita que `[true]` pase como lunes. Los días repetidos se deduplican y se guardan ordenados (`[3,1,3]` → `[1,3]`).

   Si hay errores → 422 `VALIDATION_ERROR` con `fields`. El mensaje principal sigue el mismo patrón del registro: un texto por cada tipo de error, sin repetir. Para `DAYS_REQUIRED` es "Elige al menos un día para entrenar, de lunes a viernes."

   `validate_diagnostic(raw, partial=True)` valida solo los campos presentes, con `null` todavía como faltante. Está listo para el `PATCH /profile` de la HU 6, que **no** se implementó.
4. **Perfil existente** → 409 `PROFILE_EXISTS` ("Ya completaste tu diagnóstico inicial…"), sin modificar nada. Se comprueba **después** de validar, como la unicidad del correo en el registro: un envío inválido con perfil ya creado da 422.
5. **Una transacción** (`ProfileService.create_from_diagnostic`): inserta `profiles` (`created_at = updated_at = clock.now()`), luego `profile_training_days`, y hace commit. Ante cualquier error hace rollback total.
   - **Carrera:** si dos peticiones pasan la comprobación del paso 4, la segunda choca con la PK `profiles_pkey`. Ese `IntegrityError` se captura y se convierte en 409; nunca hay días duplicados ni un 500.
   - **Otros fallos de BD:** rollback y 500 uniforme `INTERNAL_ERROR`, sin perfil parcial.
6. **Respuesta** `201 {"profile": {goal, term_weeks, fitness_level, session_minutes, training_days, has_machine_access}}`, con los días ordenados y sin `user_id` ni fechas. Es la misma forma que tendrá `GET /profile` en la HU 6.
7. **Log** `diagnostic_completed` con `user_id`, sin correo y sin las respuestas, que son datos personales de entrenamiento.

### 3.4 Modelo de datos (migración `0002_hu4_profile_schema`)

| Tabla | Columnas | Restricciones |
|---|---|---|
| `profiles` | `user_id uuid PK`, `goal text`, `term_weeks smallint`, `fitness_level text`, `session_minutes smallint`, `has_machine_access boolean`, `created_at`, `updated_at timestamptz` (todas `NOT NULL`) | FK `user_id → users(id) ON DELETE CASCADE`; `ck_profiles_goal`, `ck_profiles_fitness_level`, `ck_profiles_term_weeks`, `ck_profiles_session_minutes` |
| `profile_training_days` | `user_id uuid`, `weekday smallint` | PK `(user_id, weekday)`; FK `user_id → users(id) ON DELETE CASCADE`; `ck_profile_training_days_weekday` (`BETWEEN 1 AND 5`) |

- **Mínimo de un día:** lo valida el servicio y lo garantiza la escritura del perfil y sus días en una sola transacción.
- **`updated_at`:** servirá a la HU 6 para detectar planes desactualizados.
- **Tests de cascada de la HU 3:** pasan **sin cambios** y `CASCADE_EXCEPTIONS` sigue vacío.

### 3.5 Reemplazo del puerto `OnboardingStatus` (efecto sobre la HU 2)

`get_onboarding_status()` devuelve `ProfileOnboardingStatus(ProfileService(session, clock))`, que responde `has_profile(user_id)`. Usa la misma sesión de BD del request, porque FastAPI cachea la dependencia. Sin tocar el código de la HU 2:
- **`POST /auth/login`:** `next: "home"` con perfil y `"onboarding"` sin él (AC-4-5).
- **`GET /me`:** `onboarding_completed: true` o `false`.
- **`require_complete_profile`:** funciona de verdad: sin perfil responde 403 `ONBOARDING_REQUIRED`.
- **`verify-email`:** sigue respondiendo siempre `next: "onboarding"`, porque una cuenta recién verificada nunca tiene perfil.

**Aviso:** la sección 5.5 de [HU2.md](HU2.md), que proponía cambiar a mano `return False` por `True` para ver `next: "home"`, **ya no aplica**. Ahora basta con completar el diagnóstico.

### 3.6 Qué debe hacer la SPA

- **Formulario:** construirlo **únicamente** desde `GET /onboarding/questionnaire`, enviando los `code` tal cual con su tipo JSON. No debe tener listas propias.
- **201:** ir a la pantalla de generación del plan (HU 5).
- **409 `PROFILE_EXISTS`:** tratarlo como "ya completado" e ir a la pantalla principal.
- **422:** marcar cada pregunta indicada en `fields[].field` y mostrar `error.message`.
- **Al cargar la app:** si `GET /me` responde `onboarding_completed: false` (o el login `next: "onboarding"`), mostrar el cuestionario; si responde `true`, no volver a mostrarlo.

## 4. Cómo se hicieron las pruebas

Mismo enfoque que HU 1–3: pytest + `httpx.AsyncClient` (`ASGITransport`) contra **Postgres real** con migraciones de Alembic (ahora `0001` + `0002`) y `dependency_overrides`.

**Fixtures nuevas** (`tests/conftest.py`):
- `VALID_DIAGNOSTIC`: payload de referencia, con los días desordenados a propósito.
- `student`: usuario verificado, con sesión y **sin** perfil. `make_student(email)` crea estudiantes adicionales.
- `complete_diagnostic(token, body)`: hace el POST; con `raw=b"..."` envía bytes tal cual, por ejemplo `null`, `[]` o un cuerpo vacío.
- `protected_route`: movida desde `test_session_guards.py`.

**Técnicas destacadas**:
- **Anti-deriva (tres capas):**
  1. Se arma un envío solo con lo que devuelve el cuestionario: el primer `code` de cada pregunta `single` y todos los de la `multi`. Responde 201.
  2. **Cada uno** de los 21 `code` del cuestionario se envía con un usuario distinto. Todos responden 201 y se verifica lo guardado.
  3. La BD acepta, con inserts directos dentro de savepoints revertidos, cada valor de `options.py` y rechaza los de fuera con el `ck_*` correcto.
- **Implementación real del puerto:** AC-4-5 y la ruta protegida se prueban **sin** override de `OnboardingStatus`.
- **Carrera:** dos POST simultáneos (`asyncio.gather`) con respuestas distintas dan exactamente un 201 y un 409. Queda una sola fila en `profiles`, y los días coinciden con el 201.
- **Atomicidad ante fallo:** con `monkeypatch`, `add_training_days` inserta un día 9 que viola el CHECK en la BD. El resultado es un 500 uniforme, sin perfil ni días.
- **Mutaciones manuales:**
  - Aceptar `bool` como entero: la prueba con `training_days: [true]` falla.
  - No capturar el `IntegrityError` de la PK: la prueba de carrera falla.
- **NFR-04:** se mide el POST completo. La aserción es holgada (< 2 s) y el tiempo se imprime con `-s` y se registra como `record_property`. Se midieron **25–28 ms**.
- **Logs:** se captura la salida del `JsonFormatter` y `caplog`; `diagnostic_completed` no contiene el correo, ni los valores (`strength`, `beginner`…), ni los nombres de las preguntas.

**Resultados**: 296 pruebas (192 de HU 1–3 + 104 nuevas) pasan en Python 3.14 local y en `python:3.11-slim` (Docker).

> Nota operativa: dos corridas de pytest **no deben ejecutarse en paralelo contra la misma `TEST_DATABASE_URL`**, porque cada sesión recrea el esquema y hace `TRUNCATE`. Si se quiere paralelizar, cada corrida necesita su propia base de prueba.

### Tabla AC → pruebas

| AC | Prueba(s) |
|---|---|
| AC-4-1 | `test_ac_4_1_diagnostico_completo_se_guarda_y_permite_generar_el_plan`, `test_respuesta_no_incluye_user_id_ni_fechas`, `test_dias_repetidos_se_guardan_una_vez_y_ordenados` |
| AC-4-2 | `test_ac_4_2_pregunta_sin_responder_se_senala` (6 campos × omitido/null = 12 casos), `test_ac_4_2_cuerpo_vacio_o_no_objeto_senala_todas_las_preguntas` (`{}`, `null`, `[]`, texto, sin cuerpo) |
| AC-4-3 | `test_ac_4_3_sin_dias_pide_elegir_al_menos_uno` (ausente, `null`, `[]`) |
| AC-4-4 | `test_ac_4_4_valor_fuera_de_las_opciones_es_rechazado` (17 casos), `test_ac_4_4_un_dia_invalido_no_deja_perfil_ni_dias`, `test_ac_4_4_varios_errores_se_devuelven_juntos`, `test_check_rechaza_valores_fuera_de_la_lista`, `test_check_rechaza_dias_fuera_de_lunes_a_viernes`, unitarias `test_tipado_estricto` |
| AC-4-5 | `test_ac_4_5_con_diagnostico_completo_el_login_va_a_home`, `test_ac_4_5_sin_diagnostico_el_login_va_a_onboarding`, `test_ac_4_5_segundo_envio_devuelve_409_y_no_modifica_el_perfil`, `test_ac_4_5_un_envio_invalido_con_perfil_existente_da_422_antes_que_409`, `test_ac_4_5_guard_de_perfil_con_la_implementacion_real` |
| NFR-04 | `test_nfr_04_guardar_el_diagnostico_responde_en_menos_de_2_segundos` |
| NFR-10 | `test_nfr_10_user_id_y_campos_extra_del_cuerpo_se_ignoran` |
| NFR-11 | `no-store` verificado en `test_ac_4_1_…` y en `test_cuestionario_tiene_las_6_preguntas_cerradas_en_orden` |
| NFR-12 | `test_nfr_12_eliminar_cuenta_borra_perfil_y_dias_y_el_correo_empieza_de_cero`, `test_tablas_de_perfil_cuelgan_de_users_con_cascade` + los tests de cascada de la HU 3 sin cambios |
| NFR-13 | todo AC-4-4 + `test_anti_deriva_*` (cuestionario ↔ POST ↔ BD) |

Otras pruebas:
- **Cuestionario:** sin sesión, sesión vencida, disponible con perfil y tipos JSON de los `code`.
- **POST:** JSON mal formado, carrera, atomicidad ante fallo, sin sesión, sesión vencida, CSRF y logs.
- **Esquema:** la FK exige un usuario existente.
- **Validador:** 24 unitarias (modo parcial, campos extra, deduplicación y mensajes).

## 5. Cómo probarlo manualmente

### 5.1 Levantar el entorno

Igual que en [H1.md §5.1](H1.md). Con la BD ya creada, aplica la migración nueva:

```bash
POSTGRES_PORT=5433 docker compose up -d db
cd apps/api
.venv/bin/alembic upgrade head          # aplica 0002_hu4_profile_schema
.venv/bin/uvicorn app.main:app --reload --proxy-headers
```

### 5.2 Recorrido con curl

```bash
B=http://localhost:8000/api/v1
H=(-H "X-Requested-With: fitia" -H "Content-Type: application/json")
JAR=/tmp/fitia-cookies.txt; rm -f $JAR

# 1. Registro + verificación (token del correo impreso por uvicorn)
curl -s "${H[@]}" $B/auth/register -d '{"nickname":"Pantera","email":"ana.gomez@correounivalle.edu.co",
  "password":"contrasena-segura","program_code":"ING-SIS","accepted_terms":true}'
curl -s "${H[@]}" $B/auth/verify-email -d '{"token":"PEGA_EL_TOKEN"}'

# 2. Login → next:"onboarding"
curl -s -c $JAR "${H[@]}" $B/auth/login -d '{"email":"ana.gomez@correounivalle.edu.co","password":"contrasena-segura"}'

# 3. Cuestionario
curl -s -b $JAR $B/onboarding/questionnaire

# 4. Envíos inválidos (no se guarda nada)
curl -s -b $JAR "${H[@]}" $B/onboarding/complete -d '{}'                       # 422: las 6 preguntas
curl -s -b $JAR "${H[@]}" $B/onboarding/complete -d '{"goal":"yoga","term_weeks":"4","fitness_level":"beginner",
  "session_minutes":30,"training_days":[],"has_machine_access":"si"}'          # 422: INVALID_OPTION + DAYS_REQUIRED

# 5. Envío válido → 201
curl -s -i -b $JAR "${H[@]}" $B/onboarding/complete -d '{"goal":"strength","term_weeks":8,"fitness_level":"beginner",
  "session_minutes":30,"training_days":[5,1,3],"has_machine_access":true}'
# → 201 {"profile":{…,"training_days":[1,3,5],…}}, Cache-Control: no-store

# 6. /me → onboarding_completed:true ; login → next:"home"
curl -s -b $JAR $B/me
curl -s -c $JAR "${H[@]}" $B/auth/login -d '{"email":"ana.gomez@correounivalle.edu.co","password":"contrasena-segura"}'

# 7. Segundo envío → 409 PROFILE_EXISTS
curl -s -b $JAR "${H[@]}" $B/onboarding/complete -d '{"goal":"endurance","term_weeks":12,"fitness_level":"advanced",
  "session_minutes":60,"training_days":[2],"has_machine_access":false}'

# 8. Eliminar la cuenta → 204
curl -s -i -b $JAR "${H[@]}" $B/me/delete-account -d '{"confirm":true}'
```

### 5.3 Casos de error

| Qué probar | Petición | Esperado |
|---|---|---|
| Sin sesión | `curl -s $B/onboarding/questionnaire` | 401 `UNAUTHENTICATED` |
| Sin CSRF | POST `complete` sin `X-Requested-With` | 403 `CSRF_HEADER_MISSING` |
| Cuerpo `null` | `-d 'null'` | 422 con las 6 preguntas |
| Sin días | `"training_days": []` | 422 `DAYS_REQUIRED` ("Elige al menos un día…, de lunes a viernes.") |
| Sin acceso a máquinas | omitir `has_machine_access` | 422 `MACHINE_ACCESS_REQUIRED` |
| Número como texto | `"term_weeks": "8"` | 422 `INVALID_OPTION` |
| Booleano como día | `"training_days": [true]` | 422 `INVALID_OPTION` |
| Día sábado | `"training_days": [6]` | 422 `INVALID_OPTION` |
| Mayúsculas | `"goal": "STRENGTH"` | 422 `INVALID_OPTION` |
| Campos extra | `"user_id": "<otro>", "weight_kg": 70` | 201 para el usuario de la sesión; los extras se ignoran |
| JSON roto | `-d '{no json'` | 422 `INVALID_JSON` |

### 5.4 Revisar la BD con psql

```bash
docker exec -it fitia_postgres psql -U postgres -d fitia_db
```
```sql
SELECT p.*, array_agg(d.weekday ORDER BY d.weekday) AS dias
FROM profiles p JOIN profile_training_days d USING (user_id) GROUP BY p.user_id;

-- Los CHECK rechazan valores fuera de la lista:
INSERT INTO profile_training_days (user_id, weekday) SELECT user_id, 6 FROM profiles LIMIT 1;  -- ck_profile_training_days_weekday
UPDATE profiles SET goal = 'yoga';                                                             -- ck_profiles_goal

-- Tras eliminar la cuenta (paso 8): no queda nada
SELECT (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM profiles) AS profiles,
       (SELECT count(*) FROM profile_training_days) AS dias, (SELECT count(*) FROM sessions) AS sesiones;
```

### 5.5 Pruebas automáticas

```bash
cd apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/fitia_test .venv/bin/pytest -v
# Solo la HU 4:
TEST_DATABASE_URL=... .venv/bin/pytest -v tests/unit/test_profile_validators.py tests/integration/test_onboarding_questionnaire.py \
  tests/integration/test_onboarding_complete.py tests/integration/test_profile_schema.py
# Tiempo de NFR-04:
TEST_DATABASE_URL=... .venv/bin/pytest -s -k nfr_04
```

## 6. Supuestos tomados

1. **Días repetidos:** se deduplican y se guardan ordenados (`[1,1,3]` → `[1,3]`), como indicaba el requerimiento.
2. **`INVALID_OPTION` incluye los tipos incorrectos:** también responden `INVALID_OPTION` los tipos erróneos (un número como texto, un float o un booleano donde va un entero), y `training_days` cuando no es una lista (por ejemplo `"1"` o un objeto).
3. **Orden y mensaje de los errores:** los `fields` siguen el orden de las preguntas. El mensaje principal concatena un texto por cada **tipo** de error, sin repetir; no hay mensaje por campo porque `FieldError` solo lleva `field` y `code`, el mismo mecanismo de la HU 1.
4. **Validar antes que 409:** con un perfil ya creado, un envío inválido responde 422, no 409, igual que el registro con un correo existente.
5. **`profile_training_days` cuelga de `users`, no de `profiles`:** así lo pide el requerimiento y el test de cascada de la HU 3 lo cubre. Si la HU 6 permitiera borrar un perfil sin borrar el usuario, tendría que borrar también los días en la misma transacción.
6. **`PendingOnboardingStatus` eliminada:** no quedaba ningún uso. Para fijar el estado en pruebas está `FakeOnboardingStatus`.
7. **Dos aserciones de la HU 3 ajustadas:** `test_ac_3_2_confirmar_elimina_cuenta_datos_e_historial` y `test_ac_3_6_…` comparaban la huella completa con un diccionario de 4 tablas. Como `user_footprint` descubre tablas solo, ahora incluye `profiles` y `profile_training_days` en 0, y la comparación exacta fallaba aunque el comportamiento era correcto. Ahora comprueban "estas tablas con N filas **y todas las demás en 0**". La garantía es la misma y sirve para HU futuras sin volver a tocarlas.
8. **Sin rate limit específico** en esta HU, como indicaba el requerimiento. Las rutas exigen sesión válida.
9. **Etiquetas:** "15 min"… y "4 semanas"… se generan desde los valores. Las de objetivo, nivel, días y Sí/No están en `questionnaire.py`.

## 7. Pendiente / fuera de alcance

- **HU 5:** generación del plan con una sola llamada a Gemini. La allowlist de datos hacia la IA debe partir del DTO `DiagnosticProfile`, que no tiene `user_id`, correo ni apodo (ADR-07).
- **HU 6:** `GET /profile` (misma forma que `profile` del 201) y `PATCH /profile`, reutilizando `validate_diagnostic(..., partial=True)`, actualizando `updated_at` y reemplazando los días en la misma transacción.
- **Frontend:** formulario construido desde el cuestionario y manejo de 201, 409 y 422 según §3.6.
- **Fuera de alcance:** borrador del diagnóstico, peso, estatura, mediciones, visibilidad en ranking, resumen con IA y cualquier endpoint `/plan/*`.
