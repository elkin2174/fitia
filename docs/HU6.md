# HU 6 — Consultar y actualizar diagnóstico del estudiante

Documentación técnica de la implementación de la HU 6 (US6) del MVP FITIA: qué se construyó, cómo funciona, cómo se probó y cómo probarlo a mano. Se apoya en las historias previas [H1.md](H1.md), [HU2.md](HU2.md), [HU3.md](HU3.md), [HU4.md](HU4.md) y [HU5.md](HU5.md).

> Estado: implementado y verificado (pruebas unitarias y de integración para AC-6-1 a AC-6-5). Sin cambios de esquema de base de datos (reutiliza el esquema establecido en la migración `0002_hu4_profile_schema`).

---

## 1. Qué hace la HU 6

Permite que un estudiante con diagnóstico completado consulte y actualice las respuestas de su diagnóstico deportivo guardadas en su perfil (`profiles` y `profile_training_days`), para mantener su información vigente cuando cambien sus metas, tiempos o circunstancias en la universidad.

### Principales aspectos funcionales:
1. **Consulta del diagnóstico (`GET /api/v1/profile`):** Muestra exactamente los 6 valores persistidos del estudiante autenticado. Los campos `nickname` y `program_code` no forman parte del diagnóstico y no son editables desde esta funcionalidad.
2. **Actualización de respuestas (`PATCH /api/v1/profile` / `PUT /api/v1/profile`):** Permite modificar uno, varios o los seis campos en una única transacción atómica. Si se envía un valor inválido o no se selecciona ningún día hábil, la operación se rechaza por completo.
3. **Protección absoluta del plan vigente:** Actualizar el perfil **no regenera, no modifica, no invalida ni altera el plan actual ni sus ejercicios**. El plan vigente conserva su instantánea histórica inmutable.
4. **Mensaje informativo:** Tras guardar exitosamente, la API y la UI confirman:
   > *"Tu diagnóstico se actualizó correctamente. Los cambios se aplicarán al próximo plan que generes. Tu plan actual no ha cambiado."*
5. **Próximo plan generado:** Al solicitar una nueva rutina semanal con `POST /api/v1/plan/generate`, el sistema utiliza automáticamente las respuestas actualizadas, respetando las cuotas y los límites existentes (máximo 2 generaciones por semana).

Flujo general:

```
GET   /api/v1/profile   → 200 {profile: {goal, term_weeks, fitness_level, session_minutes, training_days, has_machine_access}}
PATCH /api/v1/profile   → 200 {profile: {...}, message: "Tu diagnóstico se actualizó..."}
PUT   /api/v1/profile   → 200 {profile: {...}, message: "Tu diagnóstico se actualizó..."}
```

Todas las mutaciones exigen la cabecera anti-CSRF `X-Requested-With: fitia`.

---

## 2. Arquitectura y archivos

Sigue el patrón de monolito modular `router → service → repository` (ADR-01).

```
apps/api/
├── app/
│   ├── main.py                               # Registra profile_router en api_v1
│   └── modules/profile/
│       ├── options.py                        # Única fuente de verdad de valores permitidos (reutilizada)
│       ├── models.py                         # Modelos SQLAlchemy Profile y ProfileTrainingDay
│       ├── schemas.py                        # DiagnosticProfile, ProfileResponse, UpdateProfileResponse
│       ├── validators.py                     # validate_diagnostic(raw, partial=True) y validación de EMPTY_UPDATE
│       ├── repository.py                     # ProfileRepository: update_profile, replace_training_days
│       ├── service.py                        # ProfileService: update_diagnostic (transacción atómica)
│       └── router.py                         # Router: GET, PATCH, PUT /profile
└── tests/
    ├── unit/
    │   ├── test_profile_validators.py        # Pruebas unitarias de validación parcial y EMPTY_UPDATE
    │   └── test_profile_service.py           # Pruebas unitarias de ProfileService
    └── integration/
        └── test_profile_diagnostic.py        # Pruebas de integración de AC-6-1 a AC-6-5

apps/web/src/features/profile/
├── types.ts                                  # Tipos TypeScript y opciones cerradas alineadas con options.py
├── api.ts                                    # Cliente fetch para GET y PATCH /api/v1/profile
└── ProfileDiagnosticView.tsx                 # Componente React de consulta y edición con feedback
```

---

## 3. Cómo funciona

### 3.1 Consulta del perfil (`GET /api/v1/profile`)

1. **Guard de Sesión y Perfil (`require_complete_profile`):**
   * Sin cookie válida → `401 UNAUTHENTICATED`.
   * Con sesión pero sin perfil completado → `403 ONBOARDING_REQUIRED`.
2. **Extracción de Identidad:** El `user_id` se extrae exclusivamente del objeto de sesión validado por el servidor; nunca proviene de query params ni headers externos (NFR-10).
3. **Respuesta:** Devuelve `200` con `{"profile": DiagnosticProfile}`, donde `training_days` se devuelve ordenado y deduplicado (`[1..5]`).

### 3.2 Actualización del diagnóstico (`PATCH /api/v1/profile` / `PUT /api/v1/profile`)

1. **Cabecera Anti-CSRF:** Exige `X-Requested-With: fitia` (ADR-04).
2. **Validación de Cuerpo:**
   * Utiliza `validate_diagnostic(raw, partial=True)`.
   * Si el payload viene vacío (`{}`) o solo con campos desconocidos que son ignorados, lanza `422 VALIDATION_ERROR` con código `EMPTY_UPDATE`.
   * Si cualquier valor contiene opciones no permitidas, tipos incorrectos (ej. booleano por entero) o lista de días vacía (`training_days: []`), rechaza la operación acumulando todos los errores en `errors` con código `422 VALIDATION_ERROR`.
3. **Optimización contra escrituras redundantes:**
   * Compara los valores limpios recibidos con los valores actuales en base de datos.
   * Si ningún campo cambió, evita escrituras en disco y retorna el perfil actual sin disparar transacciones innecesarias.
4. **Persistencia atómica:**
   * En una única transacción:
     * Actualiza las columnas escalares en `profiles` y refresca `updated_at = clock.now()`.
     * Si `training_days` está presente, elimina las filas previas en `profile_training_days` e inserta los nuevos días seleccionados.
     * Si ocurre cualquier excepción, realiza `rollback()` inmediato, garantizando cero estados inconsistentes.
5. **Auditoría limpia de logs:** Emite evento estructurado `profile_updated` con `user_id` y la lista de nombres de campos modificados (sin PII ni datos de entrenamiento).

---

## 4. Reglas de negocio e integridad

| Regla | Implementación | Garantía |
| :--- | :--- | :--- |
| **Opciones permitidas** | `apps/api/app/modules/profile/options.py` | Única fuente de verdad; no hay duplicación de opciones. |
| **Campos no editables** | `nickname` y `program_code` | Pertenecen a la entidad `users`. Son ignorados si se envían en el body y no pueden modificarse desde `/profile`. |
| **Días obligatorios** | `training_days: []` | Rechazado con código `DAYS_REQUIRED` y mensaje "Elige al menos un día para entrenar, de lunes a viernes." |
| **Tipado estricto** | `_is_int()` y validadores | Booleanos no pasan como enteros (`term_weeks: True` falla). Strings numéricos no pasan como enteros. |
| **Protección del plan vigente** | Inmutabilidad de `WeeklyPlan` | La actualización solo toca `profiles` y `profile_training_days`. `WeeklyPlan.profile_snapshot` permanece idéntico. |
| **Caché** | `NoStoreMiddleware` | Todas las respuestas bajo `/api/v1/profile` llevan `Cache-Control: no-store`. |

---

## 5. Generación del próximo plan

1. **Detección de plan desactualizado:**
   * `PlanService.current(user_id)` compara `ready.profile_snapshot != _snapshot(diagnostic)`.
   * Al haber modificado el perfil, la consulta `GET /api/v1/plan/current` responde:
     * `status: "ready"` (el plan actual sigue disponible para ver).
     * `outdated: true` (indica que hay cambios en el perfil listos para un nuevo plan).
     * `can_regenerate: true` (si el usuario no ha agotado las generaciones de la semana).
2. **Generación con datos actualizados:**
   * Al ejecutar `POST /api/v1/plan/generate`, `PlanService` recupera el diagnóstico actualizado desde `ProfileService.get_diagnostic(user_id)`.
   * Como `profile_snapshot` difiere del snapshot del plan actual, se permite la regeneración (no lanza `409 PLAN_UP_TO_DATE`).
   * La tarea asíncrona envía a la IA (Google Gemini) el nuevo snapshot con los valores actualizados.
3. **Respeto a los límites existentes:**
   * Si el estudiante ya alcanzó el límite semanal (`generation_number >= PLAN_MAX_GENERATIONS_PER_WEEK`), el sistema responde `429 REGENERATION_LIMIT`. La actualización del diagnóstico **no elude ni reinicia las cuotas semanales**.

---

## 6. Cómo se hicieron las pruebas

### Herramientas
* **Pytest 8** + `pytest-asyncio` con `httpx.AsyncClient` sobre transporte ASGI (`ASGITransport`).
* **PostgreSQL real** para pruebas de integración con esquema generado por migraciones de Alembic.
* **Fakes deterministas:** `FrozenClock` para tiempo inyectable y `FakeTextAdapter` para la IA (ninguna prueba hace llamadas de red a Gemini).

### Cobertura de Pruebas Automatizadas
* **Unitarias (`test_profile_validators.py` y `test_profile_service.py`):**
  * Validación de payload completo y parcial (`partial=True`).
  * Validación de tipos estrictos, rechazo de listas vacías y días inválidos.
  * Comprobación de mensajes unificados de error.
  * Comportamiento del servicio ante usuarios sin perfil (404), rollback ante excepciones y elusión de escrituras sin cambios.
* **Integración (`test_profile_diagnostic.py`):**
  * Verificación punto a punto de endpoints HTTP, cookies de sesión, headers CSRF, persistencia en BD y sincronización con el módulo de planes.

---

## 7. Tabla de criterios de aceptación y pruebas

| Criterio | Descripción | Pruebas Automatizadas |
| :--- | :--- | :--- |
| **AC-6-1** | Consulta del diagnóstico | `test_ac_6_1_estudiante_consulta_su_diagnostico_actual`<br>`test_ac_6_1_estudiante_sin_diagnostico_recibe_403`<br>`test_ac_6_1_sin_sesion_recibe_401`<br>`test_ac_6_1_no_expone_datos_de_otro_estudiante`<br>`test_ac_6_1_apodo_y_programa_no_forman_parte_del_diagnostico` |
| **AC-6-2** | Actualización correcta y persistencia | `test_ac_6_2_actualizacion_exitosa_persiste_y_devuelve_mensaje`<br>`test_ac_6_2_actualizacion_parcial_modifica_solo_los_campos_enviados`<br>`test_ac_6_2_consulta_posterior_devuelve_valores_guardados`<br>`test_ac_6_2_tiempo_de_respuesta_menor_a_dos_segundos`<br>`test_ac_6_2_no_modifica_apodo_ni_programa_ni_otros_usuarios`<br>`test_ac_6_2_actualizacion_con_mismos_valores_evita_escritura_innecesaria`<br>`test_ac_6_2_put_profile_soporta_actualizacion` |
| **AC-6-3** | Rechazo de datos inválidos | `test_ac_6_3_datos_invalidos_rechazan_operacion_y_preservan_estado_anterior`<br>`test_ac_6_3_training_days_vacio_falla_con_days_required`<br>`test_ac_6_3_training_days_fuera_de_rango_falla`<br>`test_ac_6_3_tipado_incorrecto_falla`<br>`test_ac_6_3_cuerpo_vacio_falla_con_empty_update`<br>`test_ac_6_3_cuerpo_solo_con_campos_desconocidos_falla` |
| **AC-6-4** | El plan vigente permanece intacto | `test_ac_6_4_plan_vigente_permanece_completamente_intacto_tras_actualizar_perfil`<br>`test_ac_6_4_no_se_consumen_cuotas_ni_limites_al_actualizar_perfil` |
| **AC-6-5** | Nuevo plan con diagnóstico actualizado | `test_ac_6_5_proximo_plan_utiliza_respuestas_actualizadas`<br>`test_ac_6_5_limite_semanal_de_regeneracion_se_respeta_estrictamente` |

---

## 8. Cómo probarlo manualmente

### 8.1 Iniciar entorno
```bash
# Iniciar base de datos local
docker compose up -d postgres

# Iniciar servidor backend
uvicorn app.main:app --reload --proxy-headers
```

### 8.2 Flujo con `curl`

1. **Iniciar sesión y capturar cookie:**
```bash
curl -i -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: fitia" \
  -d '{"email":"estudiante@correounivalle.edu.co","password":"contrasena-segura"}'
```
*(Copia el valor de `fitia_session` recibido en `Set-Cookie`).*

2. **Consultar perfil actual (`GET /api/v1/profile`):**
```bash
curl -X GET http://localhost:8000/api/v1/profile \
  -H "Cookie: fitia_session=TU_TOKEN"
```

3. **Actualizar respuestas (`PATCH /api/v1/profile`):**
```bash
curl -X PATCH http://localhost:8000/api/v1/profile \
  -H "Cookie: fitia_session=TU_TOKEN" \
  -H "X-Requested-With: fitia" \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "endurance",
    "term_weeks": 12,
    "session_minutes": 45,
    "training_days": [2, 4],
    "has_machine_access": false
  }'
```

4. **Comprobar que el plan actual no cambió y reporta `outdated: true`:**
```bash
curl -X GET http://localhost:8000/api/v1/plan/current \
  -H "Cookie: fitia_session=TU_TOKEN"
```

---

## 9. Casos de error y respuestas HTTP

* **Intento sin sesión:**
  ```json
  HTTP 401 Unauthorized
  {"error": {"code": "UNAUTHENTICATED", "message": "Debes iniciar sesión para realizar esta acción.", "fields": []}}
  ```
* **Intento sin diagnóstico inicial (onboarding incompleto):**
  ```json
  HTTP 403 Forbidden
  {"error": {"code": "ONBOARDING_REQUIRED", "message": "Debes completar el diagnóstico inicial para acceder a esta función.", "fields": []}}
  ```
* **Días de entrenamiento vacíos (`training_days: []`):**
  ```json
  HTTP 422 Unprocessable Entity
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Elige al menos un día para entrenar, de lunes a viernes.",
      "fields": [{"field": "training_days", "code": "DAYS_REQUIRED"}]
    }
  }
  ```
* **Opción inexistente (`goal: "ciclismo"`):**
  ```json
  HTTP 422 Unprocessable Entity
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Hay respuestas que no corresponden a las opciones disponibles.",
      "fields": [{"field": "goal", "code": "INVALID_OPTION"}]
    }
  }
  ```

---

## 10. Verificación en la Base de Datos

Comandos SQL para verificar la persistencia y la no modificación del plan:

```sql
-- 1. Ver respuestas actualizadas y fecha de modificación en profiles
SELECT user_id, goal, term_weeks, fitness_level, session_minutes, has_machine_access, updated_at
FROM profiles
WHERE user_id = 'UUID_DEL_USUARIO';

-- 2. Ver días de entrenamiento actualizados
SELECT weekday
FROM profile_training_days
WHERE user_id = 'UUID_DEL_USUARIO'
ORDER BY weekday;

-- 3. Demostrar que el plan vigente no sufrió alteraciones
SELECT id, status, generation_number, profile_snapshot, week_start, start_date
FROM weekly_plans
WHERE user_id = 'UUID_DEL_USUARIO';
```

---

## 11. Supuestos y decisiones tomadas

1. **Reutilización de esquema sin migración:** El esquema establecido en la migración `0002_hu4_profile_schema` ya contemplaba la columna `updated_at`, claves primarias compuestas y restricciones CHECK. No se requirió alterar la BD.
2. **Soporte `PATCH` y `PUT`:** Se implementó `PATCH /profile` para actualización de campos arbitrarios y `PUT /profile` como alias idéntico para clientes que prefieran enviar el recurso completo.
3. **Optimización idempotente:** Si el estudiante guarda el formulario sin haber cambiado ningún valor, se evita actualizar la fila en base de datos.
4. **Protección estricta de campos identitarios:** Atributos como `nickname` y `program_code` residen en la tabla `users` y son absolutamente ignorados por los serializadores del perfil.

---

## 12. Pendientes y fuera de alcance

* **Edición de apodo y consentimiento (HU 8):** La actualización de apodo o revocación de consentimientos cuenta con su propia historia de usuario y reglas de unicidad.
* **Historial de diagnósticos:** El MVP únicamente almacena el perfil vigente del estudiante y las instantáneas históricas asociadas a cada `WeeklyPlan`.
* **Notificaciones push o por email:** La confirmación de actualización se comunica sincrónicamente en la respuesta HTTP y en la interfaz web.
