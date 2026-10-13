# HU 7 — Consultar y actualizar datos del perfil del estudiante

Documentación técnica de la implementación backend de la HU 7 del MVP FITIA: qué se construyó, cómo funciona, cómo se probó y cómo probarlo a mano. Se apoya en las historias previas [H1.md](H1.md), [HU2.md](HU2.md), [HU3.md](HU3.md), [HU4.md](HU4.md), [HU5.md](HU5.md) y [HU6.md](HU6.md).

> **Estado:** implementado y verificado (605 pruebas pasando en PostgreSQL 16 con Python 3.13, 69 nuevas pruebas de HU 7: 14 de integración, 10 unitarias de service, 45 unitarias de validadores). Nueva migración Alembic `0004_hu7_profile_measurements` (bidireccional con `upgrade` y `downgrade`).

---

## 1. Qué hace la HU 7

Permite que el estudiante consulte y actualice todos los datos que conforman su perfil deportivo y físico:
- **Respuestas del diagnóstico (HU 4 / HU 6):** objetivo (`goal`), plazo en semanas (`term_weeks`), nivel físico (`fitness_level`), tiempo por sesión (`session_minutes`), días de entrenamiento (`training_days`) y preferencia de acceso a máquinas (`has_machine_access`).
- **Mediciones físicas corporales:** peso actual (`weight_kg`), estatura actual (`height_cm`) y fecha de su última actualización (`physical_updated_at`). Cada cambio genera un registro inmutable en el historial de mediciones físicas (`physical_measurements`).
- **Preferencia de visibilidad en el ranking público:** `is_public_ranking` (por defecto `true`). Al desactivarse, el usuario deja de ser listado en las consultas públicas de clasificación (HU 32, RANK-1), pero conserva íntegramente sus puntos acumulados, nivel y XP, y puede consultar su posición exacta de forma privada.
- **Gamificación y ranking privado:** puntos acumulados (`points`), nivel actual (`level`) y posición exacta en la tabla general (`ranking_position`), protegidos por sesión.

### Flujo de la API

```
GET   /api/v1/profile               → 200 {profile: {goal, term_weeks, fitness_level, session_minutes, training_days, has_machine_access, weight_kg, height_cm, physical_updated_at, is_public_ranking, points, level, ranking_position}}
PATCH /api/v1/profile               → 200 {profile: {...}, message: "Tu diagnóstico se actualizó correctamente..."}
PUT   /api/v1/profile               → 200 {profile: {...}, message: "Tu diagnóstico se actualizó correctamente..."}
GET   /api/v1/profile/measurements  → 200 {history: [{id, weight_kg, height_cm, recorded_at}, ...]}
GET   /api/v1/ranking               → 200 {items: [{position, nickname, points, level}, ...]} (público / RANK-1)
```

Todas las mutaciones exigen la cabecera anti-CSRF `X-Requested-With: fitia` y cookie de sesión `fitia_session`.

---

## 2. Arquitectura y archivos

Sigue el patrón de monolito modular `router → service → repository` (ADR-01):

```
apps/api/
├── app/
│   ├── main.py                                      # Registra profile_router y ranking_router en api_v1
│   └── modules/profile/
│       ├── options.py                               # Opciones cerradas de diagnóstico y límites de peso/estatura
│       ├── models.py                                # Modelos SQLAlchemy Profile, ProfileTrainingDay y PhysicalMeasurement
│       ├── schemas.py                               # StudentProfile, ProfileResponse, UpdateProfileResponse, RankingItem, PhysicalHistoryResponse
│       ├── validators.py                            # validate_profile_update, validate_diagnostic, constantes PROFILE_FIELDS y NON_EDITABLE_FIELDS
│       ├── repository.py                            # ProfileRepository: mediciones físicas, ranking position y ranking público
│       ├── service.py                               # ProfileService: get_profile, update_profile, get_public_ranking, get_physical_history
│       └── router.py                                # Routers: GET/PATCH/PUT /profile, GET /profile/measurements, GET /ranking
├── migrations/versions/
│   └── 0004_hu7_profile_measurements.py             # Migración Alembic: columnas de perfil y tabla physical_measurements
└── tests/
    ├── unit/
    │   ├── test_profile_hu7_validators.py           # 45 pruebas unitarias de validación y límites
    │   └── test_profile_hu7_service.py              # 10 pruebas unitarias de lógica y transaccionalidad de ProfileService
    └── integration/
        ├── test_profile_diagnostic.py               # 25 pruebas de regresión de HU 6 adaptadas al nuevo contrato
        ├── test_profile_full.py                     # 14 pruebas de integración de AC-7-1 a AC-7-8 y casos complementarios
        └── test_schema_cascade.py                   # 3 pruebas de integridad referencial CASCADE
```

---

## 3. Cómo funciona

### 3.1 Consulta del perfil (`GET /api/v1/profile`)

1. **Guard de Sesión y Perfil (`require_complete_profile`):**
   - Sin cookie válida → `401 UNAUTHENTICATED`.
   - Con sesión pero sin onboarding completado → `403 ONBOARDING_REQUIRED`.
2. **Identidad del usuario:** El `user_id` se extrae exclusivamente del objeto de sesión validado por el backend; no proviene de query params ni del body (NFR-10).
3. **Cálculo de ranking privado:** `ProfileRepository.get_ranking_position` ejecuta una consulta ordenada con `ROW_NUMBER() OVER (ORDER BY points DESC, created_at ASC)` para obtener la posición ordinal exacta entre todos los estudiantes, incluso si el usuario tiene `is_public_ranking = False`.
4. **Respuesta completa:** Retorna `200` con `StudentProfile` conteniendo los 13 atributos. Si el estudiante nunca ha ingresado peso o estatura, `weight_kg`, `height_cm` y `physical_updated_at` se retornan como `null` sin inventar valores ficticios.

### 3.2 Actualización del perfil (`PATCH /api/v1/profile` / `PUT /api/v1/profile`)

1. **Cabecera Anti-CSRF:** Exige `X-Requested-With: fitia` (ADR-04).
2. **Validación estricta de entrada (`validate_profile_update`):**
   - **Campos no editables:** Si el cuerpo incluye `points`, `level`, `ranking_position` o `physical_updated_at`, se rechaza con `422 VALIDATION_ERROR` y código `NOT_EDITABLE`.
   - **Campos de usuario ajenos:** Campos de la entidad usuario como `nickname`, `program_code` o `user_id` se ignoran silenciosamente sin modificar la tabla `users` (compatible con HU 6).
   - **Tipado estricto:** Los booleanos no se admiten como enteros (`term_weeks: True` falla). Strings numéricos no se admiten como enteros de diagnóstico.
   - **Límites de peso y estatura:** `weight_kg` debe ser numérico positivo entre 20.0 y 400.0 kg; `height_cm` debe ser numérico positivo entre 50.0 y 270.0 cm.
   - **Visibilidad en ranking:** `is_public_ranking` exige un booleano estricto (`type(v) is bool`).
   - **Cuerpo vacío o sin campos reconocidos:** Retorna `422 VALIDATION_ERROR` con código `EMPTY_UPDATE`.
3. **Optimización idempotente:** Compara los valores limpios con el perfil actual. Si nada cambió, no dispara escrituras innecesarias en la base de datos.
4. **Persistencia atómica y registro de historial:**
   - En una única transacción:
     - Si `weight_kg` o `height_cm` cambiaron frente al valor actual, se crea e inserta un registro inmutable en `physical_measurements` con `recorded_at = clock.now()`, y se actualiza `physical_updated_at = clock.now()`.
     - Se actualizan las columnas en la tabla `profiles` con `updated_at = clock.now()`.
     - Si `training_days` fue provisto, se reemplazan atómicamente las filas en `profile_training_days`.
     - Si ocurre un error, se ejecuta `rollback()`, evitando estados inconsistentes.
5. **Auditoría:** Emite evento de log estructurado `profile_updated` con `user_id` y lista de nombres de campos modificados (sin PII).

---

## 4. Contratos de API

### 4.1 Consulta del Perfil
* **Método y Ruta:** `GET /api/v1/profile`
* **Autenticación:** Cookie `fitia_session` requerida.
* **Cabeceras de respuesta:** `Cache-Control: no-store`
* **Respuesta Exitosa (`200 OK`):**
```json
{
  "profile": {
    "goal": "strength",
    "term_weeks": 8,
    "fitness_level": "intermediate",
    "session_minutes": 45,
    "training_days": [1, 3, 5],
    "has_machine_access": true,
    "weight_kg": 72.5,
    "height_cm": 175.0,
    "physical_updated_at": "2026-10-12T19:00:00-05:00",
    "is_public_ranking": true,
    "points": 150,
    "level": 2,
    "ranking_position": 1
  }
}
```

### 4.2 Actualización del Perfil
* **Método y Ruta:** `PATCH /api/v1/profile` o `PUT /api/v1/profile`
* **Autenticación:** Cookie `fitia_session` requerida.
* **Cabeceras requeridas:** `X-Requested-With: fitia`, `Content-Type: application/json`
* **Cuerpo de Solicitud (ejemplo parcial):**
```json
{
  "goal": "endurance",
  "weight_kg": 74.0,
  "is_public_ranking": false
}
```
* **Respuesta Exitosa (`200 OK`):**
```json
{
  "profile": {
    "goal": "endurance",
    "term_weeks": 8,
    "fitness_level": "intermediate",
    "session_minutes": 45,
    "training_days": [1, 3, 5],
    "has_machine_access": true,
    "weight_kg": 74.0,
    "height_cm": 175.0,
    "physical_updated_at": "2026-10-12T19:15:00-05:00",
    "is_public_ranking": false,
    "points": 150,
    "level": 2,
    "ranking_position": 1
  },
  "message": "Tu diagnóstico se actualizó correctamente. Los cambios se aplicarán al próximo plan que generes. Tu plan actual no ha cambiado."
}
```

### 4.3 Historial de Mediciones Físicas
* **Método y Ruta:** `GET /api/v1/profile/measurements`
* **Autenticación:** Cookie `fitia_session` requerida.
* **Respuesta Exitosa (`200 OK`):**
```json
{
  "history": [
    {
      "id": "161b3fc7-ea5d-4f11-9a74-a690e5026938",
      "weight_kg": 74.0,
      "height_cm": 175.0,
      "recorded_at": "2026-10-12T19:15:00-05:00"
    },
    {
      "id": "c8ea3fa5-9273-4581-b552-e1c51a0b3336",
      "weight_kg": 72.5,
      "height_cm": 175.0,
      "recorded_at": "2026-10-12T19:00:00-05:00"
    }
  ]
}
```

### 4.4 Ranking Público (HU 32, RANK-1)
* **Método y Ruta:** `GET /api/v1/ranking?limit=100`
* **Acceso:** Público / No requiere CSRF ni autenticación obligatoria.
* **Respuesta Exitosa (`200 OK`):**
```json
{
  "items": [
    {
      "position": 1,
      "nickname": "Pantera",
      "points": 150,
      "level": 2
    }
  ]
}
```
*(Los usuarios con `is_public_ranking = false` son excluidos estrictamente de esta lista).*

---

## 5. Integración con HU 4

Se reutilizan las opciones cerradas centralizadas en `apps/api/app/modules/profile/options.py`:
* `GOALS`: `"general_health"`, `"strength"`, `"endurance"`, `"weight_loss"`.
* `TERM_WEEKS`: `4`, `8`, `12`.
* `FITNESS_LEVELS`: `"beginner"`, `"intermediate"`, `"advanced"`.
* `SESSION_MINUTES`: `15`, `30`, `45`, `60`.
* `WEEKDAYS`: `1..5` (lunes a viernes).

Cualquier valor fuera de estas opciones es rechazado con `422 VALIDATION_ERROR` y código de campo `INVALID_OPTION`.

---

## 6. Integración con HU 6

* **Preferencia de acceso a máquinas:** Modificar `has_machine_access` actualiza la columna booleana en la tabla `profiles`.
* **Aplicación en la siguiente sesión (AC-7-4):**
  - La actualización del perfil no altera el plan semanal vigente en `weekly_plans`.
  - Cuando el estudiante solicita una nueva generación (`POST /api/v1/plan/generate`), el adaptador de IA recibe la preferencia vigente (`has_machine_access: false`). El nuevo plan se genera con ejercicios sin requerimiento de máquinas (`requires_machine: false`).

---

## 7. Visibilidad pública del ranking (HU 32, RANK-1)

* **Valor inicial:** La columna `is_public_ranking` tiene valor inicial `true` tanto para nuevos usuarios como para usuarios existentes mediante la migración Alembic (`server_default=text("true")`).
* **Desactivar visibilidad (AC-7-6):** Al enviar `{"is_public_ranking": false}`, el usuario deja de ser incluido en el endpoint público `GET /api/v1/ranking`. Conserva intactos sus puntos, XP, nivel y registros históricos en base de datos.
* **Reactivar visibilidad (AC-7-7):** Al enviar `{"is_public_ranking": true}`, el usuario reaparece inmediatamente en el ranking público en su posición correspondiente según sus puntos acumulados.

---

## 8. Posición privada (AC-7-8)

* El estudiante con visibilidad pública desactivada puede consultar su posición exacta y sus puntos accediendo a `GET /api/v1/profile`.
* Su posición se calcula sobre el conjunto total de estudiantes ordenados por `points DESC, created_at ASC`.
* Esta información está estrictamente protegida por sesión y no es accesible por otros usuarios a través del ranking público ni por endpoints privados de otros perfiles.

---

## 9. Historial de peso y estatura (AC-7-5)

* **Modelo relacional:** Tabla `physical_measurements` vinculada a `users.id` con `ON DELETE CASCADE`.
* **Columnas:** `id` (UUID), `user_id` (UUID), `weight_kg` (Float), `height_cm` (Float), `recorded_at` (DateTime con zona horaria).
* **Restricciones:** Restricciones CHECK para rango de peso (20 a 400 kg), rango de estatura (50 a 270 cm) y obligatoriedad de al menos un dato por registro.
* **Inmutabilidad:** Cada cambio en peso o estatura agrega una nueva fila en el historial con el timestamp `clock.now()`. Los registros anteriores se conservan para análisis de progreso.

---

## 10. Conservación de la rutina diaria

Actualizar el perfil deja la rutina diaria y el plan vigente completamente intactos:
* No se regenera ni reemplaza `WeeklyPlan`.
* No se modifican los días de entrenamiento (`plan_days`) ni los ejercicios seleccionados (`plan_exercises`).
* No se reinicia el progreso ni los estados de cumplimiento.
* El plan vigente conserva su instantánea histórica inmutable (`profile_snapshot`).

---

## 11. Cómo se hicieron las pruebas

### Entorno y Herramientas
* **Python:** 3.13.11 en Windows (con `tzdata` instalado para soporte de IANA `America/Bogota`).
* **Base de datos de prueba:** PostgreSQL 16 (contenedor Docker `fitia_postgres`), esquemas aislados por sesión de pruebas con truncado en cascada entre tests.
* **Framework:** Pytest 9.1.1 con `pytest-asyncio` 1.4.0 en modo `asyncio_mode=auto`.
* **Cliente HTTP:** `httpx.AsyncClient` con `ASGITransport`.

### Métricas reales de la suite
* **Total de pruebas ejecutadas:** 605 pruebas pasando en 207.60s (0 fallos, 0 errores).
* **Nuevas pruebas de HU 7:** 69 pruebas nuevas.
  - 45 pruebas unitarias de validadores (`tests/unit/test_profile_hu7_validators.py`).
  - 10 pruebas unitarias de servicio (`tests/unit/test_profile_hu7_service.py`).
  - 14 pruebas de integración completas (`tests/integration/test_profile_full.py`).

---

## 12. Tabla de criterios de aceptación y pruebas

| Criterio | Descripción | Pruebas Automatizadas |
| :--- | :--- | :--- |
| **AC-7-1** | Actualización de un campo válido y consulta posterior | `test_ac_7_1_actualizacion_campo_valido_y_consulta_posterior` |
| **AC-7-2** | Rechazo de datos inválidos y campos vacíos con preservación | `test_ac_7_2_valor_invalido_es_rechazado_y_mantiene_datos_anteriores`, `test_ac_7_2_campo_obligatorio_vacio_falla_con_identificacion` |
| **AC-7-3** | Salir sin guardar conserva valores anteriores | `test_ac_7_3_salir_sin_guardar_conserva_valores_anteriores` |
| **AC-7-4** | Modificar acceso a máquinas se aplica en siguiente plan | `test_ac_7_4_modificar_acceso_maquinas_persiste_y_aplica_al_proximo_plan` |
| **AC-7-5** | Actualización de peso/estatura con fecha y conservación de historial | `test_ac_7_5_actualizacion_peso_guarda_fecha_y_conserva_historial`, `test_ac_7_5_actualizacion_peso_y_estatura_simultaneas` |
| **AC-7-6** | Desactivar visibilidad oculta del ranking público conservando puntos | `test_ac_7_6_desactivar_visibilidad_oculta_de_ranking_publico_y_conserva_puntos` |
| **AC-7-7** | Reactivar visibilidad reaparece en ranking con puntos actuales | `test_ac_7_7_reactivar_visibilidad_reaparece_en_ranking` |
| **AC-7-8** | Consulta privada de posición exacta y puntos por usuario oculto | `test_ac_7_8_usuario_oculto_consulta_su_posicion_exacta_de_forma_privada` |
| **Complementarias** | Autenticación, campos no editables, inmutabilidad de plan vigente | `test_usuario_no_autenticado_recibe_401`, `test_rechaza_campos_no_editables_con_422_not_editable`, `test_plan_vigente_permanece_intacto_tras_actualizar_perfil_hu7`, `test_usuarios_nuevos_tienen_is_public_ranking_true_por_defecto` |

---

## 13. Cómo probarlo manualmente

### 13.1 Iniciar entorno
```bash
# Asegurar contenedor de PostgreSQL activo
docker compose up -d postgres

# Ejecutar migraciones Alembic
alembic upgrade head

# Iniciar servidor backend FastAPI
uvicorn app.main:app --reload
```

### 13.2 Flujo con `curl`

1. **Iniciar sesión:**
```bash
curl -i -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: fitia" \
  -d '{"email":"ana.gomez@correounivalle.edu.co","password":"contrasena-segura"}'
```
*(Copiar la cookie `fitia_session` recibida).*

2. **Consultar perfil completo (`GET /api/v1/profile`):**
```bash
curl -X GET http://localhost:8000/api/v1/profile \
  -H "Cookie: fitia_session=TU_COOKIE"
```

3. **Actualizar peso, estatura y desactivar visibilidad en ranking (`PATCH /api/v1/profile`):**
```bash
curl -X PATCH http://localhost:8000/api/v1/profile \
  -H "Cookie: fitia_session=TU_COOKIE" \
  -H "X-Requested-With: fitia" \
  -H "Content-Type: application/json" \
  -d '{
    "weight_kg": 73.5,
    "height_cm": 176.0,
    "is_public_ranking": false
  }'
```

4. **Verificar que el usuario no aparece en el ranking público (`GET /api/v1/ranking`):**
```bash
curl -X GET http://localhost:8000/api/v1/ranking
```

5. **Consultar historial físico (`GET /api/v1/profile/measurements`):**
```bash
curl -X GET http://localhost:8000/api/v1/profile/measurements \
  -H "Cookie: fitia_session=TU_COOKIE"
```

---

## 14. Casos de error

* **Intento sin sesión (`401 UNAUTHORIZED`):**
  ```json
  {"error": {"code": "UNAUTHENTICATED", "message": "Debes iniciar sesión para realizar esta acción.", "fields": []}}
  ```
* **Intento de mutar campos protegidos no editables (`422 VALIDATION_ERROR`):**
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Hay campos que no son editables.",
      "fields": [{"field": "points", "code": "NOT_EDITABLE"}]
    }
  }
  ```
* **Peso o estatura fuera de límites (`422 VALIDATION_ERROR`):**
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Hay respuestas que no corresponden a las opciones disponibles.",
      "fields": [{"field": "weight_kg", "code": "INVALID_OPTION"}]
    }
  }
  ```
* **Cuerpo de actualización vacío (`422 VALIDATION_ERROR`):**
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Debes incluir al menos un campo del perfil para actualizar.",
      "fields": [{"field": "body", "code": "EMPTY_UPDATE"}]
    }
  }
  ```

---

## 15. Verificación de la base de datos

Consultas SQL compatibles para auditar el estado en PostgreSQL:

```sql
-- 1. Consultar perfil con peso, estatura, visibilidad y puntos
SELECT user_id, goal, term_weeks, fitness_level, session_minutes, has_machine_access,
       weight_kg, height_cm, physical_updated_at, is_public_ranking, points, level
FROM profiles
WHERE user_id = 'UUID_DEL_USUARIO';

-- 2. Consultar historial físico inmutable ordenado por fecha
SELECT id, user_id, weight_kg, height_cm, recorded_at
FROM physical_measurements
WHERE user_id = 'UUID_DEL_USUARIO'
ORDER BY recorded_at DESC;

-- 3. Calcular posición exacta privada en el ranking
SELECT rank FROM (
    SELECT user_id, ROW_NUMBER() OVER (ORDER BY points DESC, created_at ASC) as rank
    FROM profiles
) ranked WHERE user_id = 'UUID_DEL_USUARIO';

-- 4. Comprobar que usuarios con is_public_ranking=false no están en ranking público
SELECT u.nickname, p.points, p.level
FROM profiles p
JOIN users u ON u.id = p.user_id
WHERE p.is_public_ranking = TRUE
ORDER BY p.points DESC, p.created_at ASC;
```

---

## 16. Supuestos y decisiones tomadas

1. **Longitud de identificador de migración Alembic:** La columna `version_num` de `alembic_version` tiene límite de 32 caracteres. El identificador de la migración se nombró `0004_hu7_profile_measurements` (29 caracteres) para garantizar compatibilidad con PostgreSQL.
2. **Rechazo de campos de gamificación no editables:** Atributos como `points`, `level` y `ranking_position` se rechazan con código `NOT_EDITABLE` si son enviados en la solicitud de actualización de perfil, garantizando que el usuario no pueda alterar su puntuación.
3. **Persistencia temporal atómica:** Cada actualización que incluya peso o estatura genera simultáneamente un registro histórico inmutable en `physical_measurements` y actualiza `profiles.physical_updated_at` con `clock.now()`.
4. **Ranking público con exclusión:** Se implementó el endpoint `GET /api/v1/ranking` correspondiente a HU 32 (RANK-1) para materializar y validar la exclusión de usuarios ocultos y su reactivación.

---

## 17. Pendientes y fuera de alcance

* **Módulo de gamificación y asignación de puntos por retos (Épica 3: HU 14):** La lógica de ganar puntos completando entrenamientos o retos se vinculará en sus respectivas historias.
* **Cálculo de IMC o métricas de composición corporal:** Fuera del alcance del MVP base.
* **Notificaciones por cambios de posición en ranking:** No contempladas en HU 7.
