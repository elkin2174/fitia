# HU 2 — Inicio de sesión

Documentación de la implementación backend de la HU 2 del MVP FITIA: qué se construyó, cómo funciona, cómo se probó y cómo probarlo a mano. Se apoya en la HU 1 ([H1.md](H1.md)).

> Estado: implementado y probado. 144 pruebas pasando (99 de la HU 1 + 45 nuevas) en Python 3.14 local y 3.11 en Docker. Sin commit todavía. Sin cambios de esquema (no hubo migración `0002`).

---

## 1. Qué hace la HU 2

Un estudiante registrado y con el correo verificado inicia sesión con su correo institucional y su contraseña. La API crea una sesión nueva (cookie `fitia_session`) y le indica al frontend a dónde ir: `next: "home"` si ya completó el diagnóstico inicial (HU 4) o `next: "onboarding"` si no.

Además deja los **guards de sesión** que usarán todas las HU siguientes: sin sesión válida cualquier endpoint protegido responde 401, y el guard "S+P" exige además el diagnóstico completo (403).

```
POST /api/v1/auth/login   → 200 {user, next} + cookie fitia_session      (pública, exige X-Requested-With)
GET  /api/v1/me           → 200 {id, nickname, program, onboarding_completed}  (requiere sesión)
```

## 2. Arquitectura y archivos

Mismo monolito modular `router → service → repository`. Archivos **nuevos**:

```
apps/api/app/modules/auth/dependencies.py   # guards: get_current_session, get_current_user, require_complete_profile
apps/api/app/modules/onboarding/status.py   # puerto OnboardingStatus + implementación provisional
apps/api/tests/integration/test_login.py
apps/api/tests/integration/test_session_guards.py
```

Archivos **modificados** (cambios mínimos, la HU 1 no cambia de comportamiento):

| Archivo | Cambio |
|---|---|
| `core/config.py` | `SESSION_TOUCH_INTERVAL_MINUTES`, `RATE_LIMIT_LOGIN_WINDOW_MINUTES`, `RATE_LIMIT_LOGIN_PER_IP`, `RATE_LIMIT_LOGIN_PER_EMAIL` |
| `core/rate_limit.py` | `hit()` se divide en `check()` (consulta sin registrar) + `record()`; nuevo `clear()`. `hit()` se comporta igual que antes |
| `core/security.py` | `password_needs_rehash()` (Argon2 `check_needs_rehash`) |
| `modules/auth/cookies.py` | `delete_session_cookie()` y `session_cookie_deletion_header()` (reutilizables por el logout de la HU 3) |
| `modules/auth/repository.py` | `get_user_with_program_by_email`, `update_password_hash`, `get_active_session`, `touch_session` |
| `modules/auth/service.py` | `AuthService.login`, `AuthService.get_me`; el servicio recibe `OnboardingStatus` |
| `modules/auth/schemas.py` | `LoginRequest`, `LoginResponse`, `MeResponse` |
| `modules/auth/router.py` | `POST /auth/login`, `GET /me` |
| `.env.example` | variables nuevas |
| `tests/conftest.py`, `tests/fakes.py` | fixtures `make_user`, `verified_user`, `pending_user`, `login`, `onboarding`; `FakeOnboardingStatus` |

## 3. Cómo funciona

### 3.1 Login (`POST /api/v1/auth/login`)

Cuerpo: `{ email, password }`. Pasos en `AuthService.login`, en este orden:

1. **Rate limit, antes de cualquier consulta o Argon2** (para que el login no sea un vector de DoS):
   - por IP: cuenta **todos** los intentos (`RATE_LIMIT_LOGIN_PER_IP`, 100 por defecto, alto porque el campus comparte IP);
   - por correo: se **consulta** el contador de fallos del hash SHA-256 del correo normalizado (nunca el correo en claro). Solo se registran intentos fallidos (`ACCOUNT_NOT_FOUND` e `INVALID_CREDENTIALS`) y el contador se borra tras un login exitoso. Por defecto, 5 fallos en 15 min.
   - Excedido → 429 `RATE_LIMITED` con `Retry-After`.
2. **Normalización** del correo (`trim + lower`), reutilizando `validators.py`.
3. **Validación** (422 `VALIDATION_ERROR`, todos los errores juntos):
   - `INVALID_EMAIL`: correo vacío, mal formado o con más de un `@`.
   - `REQUIRED`: contraseña vacía.
   - `PASSWORD_TOO_LONG`: más de 128 caracteres.
   - Aquí **no** se aplica el mínimo de 8 caracteres (es solo del registro).
4. **Búsqueda de la cuenta**. Si no existe, o el dominio no es institucional (no se consulta la BD), responde 404 `ACCOUNT_NOT_FOUND` con el mensaje "Este correo no está registrado en FITIA. Crea una cuenta para empezar." (AC-2-3). El frontend arma el enlace al registro a partir del código.
5. **Contraseña**: Argon2id en un threadpool. Si falla → 401 `INVALID_CREDENTIALS` con un mensaje genérico (AC-2-2).
6. **Verificación del correo, solo con la contraseña correcta**. Si `email_verified_at IS NULL` → 403 `EMAIL_NOT_VERIFIED` y no se crea sesión (AC-2-6). El frontend ofrece reenviar con el endpoint existente `POST /auth/resend-verification`. Como se comprueba después de la contraseña, alguien que no la conoce no puede averiguar si la cuenta está verificada.
7. **Rehash**: si el hash usa parámetros antiguos (`check_needs_rehash`), se recalcula y se guarda.
8. **Sesión nueva siempre** con `issue_session`, la misma función de la HU 1. Nunca se reutiliza una sesión existente, aunque llegue una cookie previa (evita fijación de sesión). Se permiten varias sesiones por usuario, una por dispositivo. Se fija la cookie `fitia_session` con `cookies.py` y se envía `Cache-Control: no-store`.
9. **`next`**: `"home"` si `OnboardingStatus.is_completed(user_id)` es verdadero; si no, `"onboarding"` (AC-2-4).
10. **Reinicio** del contador de fallos del correo.

Respuesta 200: `{"user": {"id", "nickname", "program": {"code", "name"}}, "next": "onboarding" | "home"}`. Sin correo ni hashes.

### 3.2 `GET /api/v1/me`

Requiere sesión (`get_current_user`). Devuelve `{id, nickname, program: {code, name}, onboarding_completed}` con `Cache-Control: no-store`. El `id` sale **siempre** de la sesión; cualquier `id` en el query o en el cuerpo se ignora (NFR-10). Es lo que usa la SPA al cargar para saber si hay sesión activa y para los guards de rutas. Al ser GET, no exige el encabezado CSRF.

### 3.3 Guards de sesión (`modules/auth/dependencies.py`)

**`get_current_session`** devuelve un `CurrentSession(id, expires_at, user: CurrentUser)`:
- lee la cookie `fitia_session`, calcula su SHA-256 y busca, con un solo JOIN, la sesión con `expires_at > now` (reloj inyectable) junto con su usuario;
- responde 401 `UNAUTHENTICATED` y borra la cookie (`Set-Cookie: fitia_session=""; Max-Age=0`) en cualquiera de estos casos: no hay cookie, el token no existe, la sesión venció, el usuario fue eliminado (el `CASCADE` borra sus sesiones) o la cuenta no está verificada;
- **expiración deslizante**: si `last_seen_at` tiene `SESSION_TOUCH_INTERVAL_MINUTES` o más (10 por defecto), actualiza `last_seen_at = now` y `expires_at = now + SESSION_TTL_DAYS` y vuelve a emitir la cookie con la nueva expiración. Si no ha pasado ese intervalo, **no escribe en la BD**;
- añade `Cache-Control: no-store` a la respuesta autenticada (NFR-11 parcial).

**`get_current_user`** devuelve `CurrentUser(id, nickname, program_code, role)`. Las HU siguientes deben filtrar siempre por `user.id`.

**`require_complete_profile`** (guard "S+P") pide sesión y diagnóstico completo. Si el diagnóstico está incompleto → 403 `ONBOARDING_REQUIRED`, que la SPA traduce en una redirección a la HU 4.

Uso en una HU futura:

```python
@router.get("/rutinas")
async def rutinas(user: CurrentUser = Depends(require_complete_profile)) -> ...:
    return await service.listar(user.id)
```

### 3.4 Estado del diagnóstico: puerto `OnboardingStatus`

La tabla `profiles` (HU 4) todavía no existe, así que no se creó. En `modules/onboarding/status.py`:

- `OnboardingStatus` es un puerto con `async def is_completed(user_id) -> bool`.
- `PendingOnboardingStatus` es la implementación por defecto: devuelve siempre `False`. Por eso, hoy todo login responde `next: "onboarding"` y `/me` responde `onboarding_completed: false`.
- **Punto de reemplazo (HU 4):** la función `get_onboarding_status()` del mismo archivo. Debe devolver una implementación que consulte `profiles`; el comentario en el código muestra cómo. Ni `login`, ni `/me`, ni el guard necesitan cambios.

### 3.5 Base de datos

Sin cambios de esquema. Se usan `users` (`password_hash`, `email_verified_at`) y `sessions` (`token_hash`, `expires_at`, `last_seen_at`) de la migración `0001`.

## 4. Cómo se hicieron las pruebas

Mismo enfoque que la HU 1: pytest + pytest-asyncio + `httpx.AsyncClient` (`ASGITransport`) contra **Postgres real**, con las migraciones reales de Alembic y `dependency_overrides` para la BD, `FrozenClock`, `FakeMailer`, `Settings` y un `RateLimiter` nuevo por test.

**Fixtures nuevas** (`tests/conftest.py`):
- `make_user(email, verified=..., password_hash=...)` inserta un usuario directamente en la BD. Sobre ella se construyen `verified_user` (listo para iniciar sesión) y `pending_user` (sin verificar).
- `login(email, password)` llama al endpoint.
- `onboarding` sustituye el puerto por un `FakeOnboardingStatus` cuyo `completed` se cambia dentro del test.
- `session_token(response)` y `with_session(token)`: el cliente de pruebas usa `http`, así que la cookie `Secure` se envía a mano en el encabezado `Cookie`.

**Técnicas destacadas**:
- **Argon2 no se ejecuta antes del límite:** un espía sobre `verify_password` cuenta sus invocaciones, y se comprueba que el 429 llega sin ninguna nueva.
- **Ruta protegida solo en tests:** se añade con `app.add_api_route` en una fixture y se elimina al terminar. Así se prueba `require_complete_profile` sin publicar rutas falsas.
- **Expiración deslizante:** con `FrozenClock` se avanza 9 min (sin escritura en BD ni nueva cookie), 10 min (`expires_at` se extiende y se reemite la cookie) y tres saltos de 20 días (la sesión sigue viva más allá de los 30 días desde el login).
- **Rehash:** se guarda un hash Argon2id con parámetros débiles (`t=1, m=8192, p=1`). Tras el login, el hash cambia y ya no necesita rehash.
- **Logs sin PII:** se captura la salida del `JsonFormatter` y de `caplog` durante logins fallidos, y se comprueba que no aparecen ni el correo ni la contraseña.
- **NFR-02:** se mide el login completo con Argon2 real. La aserción es holgada (< 3 s) y el tiempo se imprime con `-s` y se registra como `record_property`. Se midieron **71–73 ms**.

**Resultados**: 144 pruebas (99 de la HU 1 sin cambios + 45 nuevas) pasan en Python 3.14 local y en `python:3.11-slim` (Docker).

### Tabla AC → pruebas

| AC | Prueba(s) |
|---|---|
| AC-2-1 | `test_ac_2_1_credenciales_correctas_inician_sesion_y_dan_acceso` |
| AC-2-2 | `test_ac_2_2_contrasena_incorrecta_no_inicia_sesion` |
| AC-2-3 | `test_ac_2_3_correo_no_registrado_invita_a_registrarse` (institucional inexistente y `@gmail.com`) |
| AC-2-4 | `test_ac_2_4_sin_diagnostico_completo_lleva_a_onboarding`, `test_ac_2_4_por_defecto_el_diagnostico_se_considera_incompleto`, `test_ac_2_1_…` (`next: "home"`) |
| AC-2-5 | `test_ac_2_5_me_sin_cookie_devuelve_401`, `test_ac_2_5_cookie_inventada_devuelve_401_y_borra_la_cookie`, `test_ac_2_5_sesion_vencida_devuelve_401`, `test_ac_2_5_usuario_eliminado_invalida_la_sesion`, `test_ac_2_5_usuario_no_verificado_con_sesion_devuelve_401`, `test_ac_2_5_guard_de_perfil_exige_diagnostico_completo`, `test_ac_2_5_guard_de_perfil_sin_sesion_devuelve_401` |
| AC-2-6 | `test_ac_2_6_cuenta_sin_verificar_no_inicia_sesion`, `test_ac_2_6_cuenta_sin_verificar_con_contrasena_incorrecta_no_revela_su_estado`, `test_ac_2_6_flujo_completo_pendiente_verificar_y_luego_iniciar_sesion` |
| NFR-02 | `test_nfr_02_login_completo_responde_en_menos_de_3_segundos` |
| NFR-08 | `test_hash_con_parametros_antiguos_se_actualiza_tras_login` |
| NFR-10 | `test_nfr_10_me_ignora_ids_en_query`, guards AC-2-5 |
| NFR-11 (parcial) | aserciones de `Cache-Control: no-store` en login, `/me`, 401 y la ruta protegida |

Otras pruebas:
- **Normalización:** correo con espacios y mayúsculas.
- **Validación:** cuerpo vacío, correo mal formado, contraseña de más de 128 caracteres, y que no se aplique el mínimo de 8.
- **Seguridad:**
  - CSRF (403);
  - respuestas sin correo ni hashes;
  - el token de sesión solo se guarda como hash;
  - cada login crea una sesión distinta y ambas conviven;
  - un login con una cookie previa no la reutiliza.
- **Rate limit:**
  - 5 fallos y luego 429, sin que corra Argon2;
  - un login exitoso reinicia el contador;
  - los logins exitosos no cuentan para el límite;
  - los correos inexistentes sí cuentan como fallo;
  - el límite por IP.
- **`/me`:** no exige CSRF y no expone el correo.
- **Sesión deslizante:** dentro del intervalo, al pasarlo y más allá de 30 días.
- **Unitarias:** `check`, `record` y `clear` del limiter, y `password_needs_rehash`.

## 5. Cómo probarlo manualmente

### 5.1 Levantar el entorno

Igual que en [H1.md §5.1](H1.md). Resumen (puerto 5433 porque en tu máquina hay un Postgres en 5432):

```bash
POSTGRES_PORT=5433 docker compose up -d db
cd apps/api
.venv/bin/alembic upgrade head
.venv/bin/python -m seeds.load_academic_programs
.venv/bin/uvicorn app.main:app --reload --proxy-headers
```

`.env` con `COOKIE_SECURE=false` (si no, el navegador y `curl -b` no reenviarán la cookie por HTTP) y `MAIL_PROVIDER=console`.

### 5.2 Recorrido completo con curl

```bash
B=http://localhost:8000/api/v1
H=(-H "X-Requested-With: fitia" -H "Content-Type: application/json")
JAR=/tmp/fitia-cookies.txt

# 1. Registro
curl -s "${H[@]}" $B/auth/register -d '{"nickname":"Pantera","email":"ana.gomez@correounivalle.edu.co",
  "password":"contrasena-segura","program_code":"ING-SIS","accepted_terms":true}'
# → 201 {"status":"pending_verification"}

# 2. Login antes de verificar (AC-2-6)
curl -s "${H[@]}" $B/auth/login -d '{"email":"ana.gomez@correounivalle.edu.co","password":"contrasena-segura"}'
# → 403 EMAIL_NOT_VERIFIED

# 3. Verificar: copia el token del correo impreso en la terminal de uvicorn
TOKEN=pega_aqui_el_token
curl -s "${H[@]}" $B/auth/verify-email -d "{\"token\":\"$TOKEN\"}"
# → 200 (esta respuesta también crea una sesión)

# 4. Login (AC-2-1, con normalización del correo) guardando la cookie
curl -s -i -c $JAR "${H[@]}" $B/auth/login \
  -d '{"email":"  ANA.Gomez@correounivalle.edu.co ","password":"contrasena-segura"}'
# → 200, Set-Cookie: fitia_session=...; HttpOnly; SameSite=lax, Cache-Control: no-store,
#   {"user":{...},"next":"onboarding"}   (onboarding hasta que exista la HU 4)

# 5. /me con la cookie
curl -s -i -b $JAR $B/me
# → 200 {"id":...,"nickname":"Pantera","program":{...},"onboarding_completed":false}, Cache-Control: no-store
```

### 5.3 Casos de error

| Qué probar | Petición | Esperado |
|---|---|---|
| Sin sesión (AC-2-5) | `curl -s $B/me` | 401 `UNAUTHENTICATED` |
| Cookie inventada | `curl -s -i -H "Cookie: fitia_session=x" $B/me` | 401 y `Set-Cookie: fitia_session=""; Max-Age=0` |
| Contraseña incorrecta (AC-2-2) | login con `"password":"mala"` | 401 `INVALID_CREDENTIALS`, sin cookie |
| Correo no registrado (AC-2-3) | `nadie@correounivalle.edu.co` | 404 `ACCOUNT_NOT_FOUND` |
| Otro dominio | `ana@gmail.com` | 404 `ACCOUNT_NOT_FOUND` |
| Sin CSRF | login sin `X-Requested-With` | 403 `CSRF_HEADER_MISSING` |
| Cuerpo vacío | `-d '{}'` | 422 con `INVALID_EMAIL` y `REQUIRED` |
| Contraseña > 128 | `"password"` de 129 caracteres | 422 `PASSWORD_TOO_LONG` |
| Rate limit | 5 logins fallidos al mismo correo y luego uno correcto | el 6.º da 429 con `Retry-After` (incluso con la contraseña buena) |
| Reinicio del contador | 4 fallos, 1 login correcto, 5 fallos más | todos 401; el siguiente, 429 |

El rate limit vive en memoria: reinicia uvicorn para limpiarlo.

### 5.4 Revisar la BD

```bash
docker exec -it fitia_postgres psql -U postgres -d fitia_db
```
```sql
SELECT user_id, left(token_hash, 16), expires_at, last_seen_at FROM sessions;  -- solo hashes, una fila por login
-- Simular sesión vencida (luego /me → 401):
UPDATE sessions SET expires_at = now() - interval '1 second';
-- Forzar la expiración deslizante en la próxima petición:
UPDATE sessions SET last_seen_at = now() - interval '11 minutes';
-- Simular cuenta pendiente para probar AC-2-6:
UPDATE users SET email_verified_at = NULL;
```

### 5.5 Probar `next: "home"` antes de que exista la HU 4

Hoy no hay forma de completar el diagnóstico desde la API. Para verlo a mano, cambia temporalmente el `return False` de `PendingOnboardingStatus.is_completed` (en `app/modules/onboarding/status.py`) por `True`: el login responderá `next: "home"` y `/me` responderá `onboarding_completed: true`. Las pruebas automáticas cubren ese caso con `FakeOnboardingStatus`.

### 5.6 Pruebas automáticas

```bash
cd apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/fitia_test .venv/bin/pytest -v
# Solo la HU 2:
TEST_DATABASE_URL=... .venv/bin/pytest -v tests/integration/test_login.py tests/integration/test_session_guards.py
# Ver el tiempo medido de NFR-02:
TEST_DATABASE_URL=... .venv/bin/pytest -s -k nfr_02
```

## 6. Supuestos tomados

1. **Sesión hasta cerrar sesión:** se implementa como expiración deslizante de 30 días por inactividad (`SESSION_TTL_DAYS`). Al extenderse, también se reemite la cookie; si no, el navegador la descartaría a los 30 días del login aunque el servidor la siguiera aceptando.
2. **Rate limit del login:**
   - Ventana de 15 min, 100 intentos por IP y 5 fallos por correo.
   - El 403 `EMAIL_NOT_VERIFIED` no cuenta como fallo (la contraseña era correcta) y tampoco reinicia el contador.
   - Los 422 cuentan para el límite por IP, pero no para el del correo.
3. **Enumeración aceptada (S-03 / R-08):** el 404 `ACCOUNT_NOT_FOUND` revela si un correo existe, y además responde más rápido que un 401 porque no ejecuta Argon2. Se mitiga con el rate limit por IP y por correo.
4. **Mismo código para cualquier dominio:** un correo de otro dominio responde 404 `ACCOUNT_NOT_FOUND` y no `DOMAIN_NOT_ALLOWED`, porque no puede existir ninguna cuenta así (lo impide el CHECK de la BD).
5. **Bloqueo por correo ajeno:** el límite por correo se aplica también cuando se envía la contraseña correcta. Un tercero podría bloquear temporalmente a un usuario con 5 fallos (15 min como máximo). Es el costo aceptado de no ejecutar Argon2 antes del límite.
6. **`verify-email` sigue respondiendo siempre `next: "onboarding"`**, como en la HU 1, porque una cuenta recién verificada nunca tiene el diagnóstico hecho.
7. **Usuario eliminado o no verificado con sesión activa:** el guard responde 401 y borra la cookie. No marca la sesión en la BD; eso corresponde a la HU 3.
8. **Escritura dentro del guard:** la extensión deslizante hace `commit` en la misma sesión de BD del request, antes de la lógica del endpoint.
9. **Mensajes al usuario:**
   - 404: "Este correo no está registrado en FITIA. Crea una cuenta para empezar."
   - 401: "El correo o la contraseña no son correctos."
   - 403 de verificación: "Debes verificar tu correo antes de iniciar sesión. Revisa tu bandeja o solicita un nuevo enlace."
10. El rate limit sigue siendo en memoria y por proceso (igual que en la HU 1). Con varias instancias en Render habría que moverlo a un almacén compartido.

## 7. Pendiente / fuera de alcance

- **HU 3:** logout y eliminación de cuenta. Ya existen `delete_session_cookie` y `get_current_session`, que devuelve el `id` de la sesión para invalidarla. Faltan también `Cache-Control: no-store` en el resto de las respuestas (NFR-11 completo) y la revocación de sesiones.
- **HU 4:** reemplazar `get_onboarding_status()` por una implementación que consulte `profiles`.
- **Frontend:**
  - pantalla de login;
  - manejo de `ACCOUNT_NOT_FOUND` (enlace al registro) y de `EMAIL_NOT_VERIFIED` (botón de reenviar);
  - guards de ruta basados en `GET /me`;
  - redirección ante 401 y ante `ONBOARDING_REQUIRED`.
- Fuera de alcance: recuperación de contraseña, "recordarme", OAuth y 2FA.
