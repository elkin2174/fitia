# HU 3 — Cerrar sesión y eliminar cuenta

Documentación de la implementación backend de la HU 3 del MVP FITIA: qué se construyó, cómo funciona, cómo se probó y cómo probarlo a mano. Se apoya en la HU 1 ([H1.md](H1.md)) y la HU 2 ([HU2.md](HU2.md)).

> Estado: implementado y probado. 192 pruebas pasando (144 de HU 1–2 + 48 nuevas) en Python 3.14 local y 3.11 en Docker. Sin commit todavía. Sin cambios de esquema: el test de cascada confirmó que todas las FK de la migración `0001` ya eran `ON DELETE CASCADE`, así que no hizo falta migración `0002`.

---

## 1. Qué hace la HU 3

- **Cerrar sesión**: invalida en el servidor la sesión actual (borra su fila en `sessions`) y borra la cookie. Un token copiado antes del logout deja de servir de inmediato.
- **Eliminar cuenta**: con confirmación explícita, borra de forma definitiva el usuario y todo lo que cuelga de él. Sus sesiones en otros dispositivos mueren al instante, y el mismo correo puede registrarse de nuevo desde cero.
- **NFR-11 completo**: `Cache-Control: no-store` en todas las respuestas de `/api/v1`, también las de error. Se exceptúan los GET públicos que sí pueden cachearse.
- **Garantía de esquema para HU futuras**: un test contra la BD real hace fallar el CI si una migración agrega datos de usuario sin `ON DELETE CASCADE`.

```
POST /api/v1/auth/logout          → 204 (requiere sesión; no exige diagnóstico completo)
POST /api/v1/me/delete-account    → 204 con {"confirm": true}; 400 sin confirmación
```

Ambas son mutaciones, así que exigen `X-Requested-With: fitia`.

## 2. Arquitectura y archivos

Archivos **nuevos**:

```
apps/api/app/core/cache_control.py                 # NoStoreMiddleware (ASGI puro)
apps/api/tests/integration/test_logout.py
apps/api/tests/integration/test_delete_account.py
apps/api/tests/integration/test_schema_cascade.py
apps/api/tests/integration/test_no_store.py
```

Archivos **modificados** (cambios mínimos, HU 1 y 2 sin cambios de comportamiento):

| Archivo | Cambio |
|---|---|
| `modules/auth/schemas.py` | `DeleteAccountRequest { confirm: StrictBool \| None }` |
| `modules/auth/repository.py` | `delete_session(session_id)`, `delete_user(user_id) -> bool` (un único `DELETE … RETURNING`) |
| `modules/auth/service.py` | `AuthService.logout`, `AuthService.delete_account` |
| `modules/auth/router.py` | `POST /auth/logout`, `POST /me/delete-account` |
| `modules/auth/dependencies.py` | `_unauthenticated` pasa a ser pública (`unauthenticated_error`) para el 401 de carrera del servicio |
| `core/errors.py` | el 500 genérico también lleva `no-store` (lo emite `ServerErrorMiddleware`, por fuera del middleware) |
| `main.py` | registra `NoStoreMiddleware` |
| `tests/conftest.py` | fixture `user_footprint` (cuenta las filas de un usuario en todas las tablas con `user_id`) |

## 3. Cómo funciona

### 3.1 Cerrar sesión (`POST /api/v1/auth/logout`)

1. Guard `get_current_session`. **No** se usa `require_complete_profile`: un usuario con el diagnóstico incompleto también puede salir.
2. `AuthService.logout(current.id)` borra **solo la fila de la sesión actual** y hace commit. Las sesiones de otros dispositivos siguen vivas (supuesto).
3. Responde `204` sin cuerpo, con un único `Set-Cookie` de borrado (`fitia_session=""; Max-Age=0; Path=/; SameSite=lax; HttpOnly`, y `Secure` según `COOKIE_SECURE`, los mismos atributos con que se fijó) y con `Cache-Control: no-store`.
4. Sin sesión válida → 401 `UNAUTHENTICATED` (lo da el guard). La SPA debe tratar ese 401 como "ya estaba cerrada" y continuar a la bienvenida.

**Cuidado con la expiración deslizante.** `get_current_session` puede reemitir la cookie viva en el `Response` inyectado. Si el endpoint usara ese mismo objeto, la respuesta llevaría dos `Set-Cookie`: el de la cookie viva y el de borrado. Para evitarlo, el endpoint devuelve una `Response(204)` **nueva**: FastAPI descarta los encabezados del `Response` inyectado cuando el endpoint devuelve su propio `Response`. El test `test_ac_3_1_no_deja_cookie_viva_aunque_el_guard_la_reemita` fuerza la reemisión y comprueba que solo queda el `Set-Cookie` de borrado; se validó que falla si se usa el `Response` inyectado.

### 3.2 Eliminar cuenta (`POST /api/v1/me/delete-account`)

Cuerpo: `{"confirm": true}`.

1. Guard `get_current_session`, igual que el logout: no exige diagnóstico.
2. El cuerpo es **opcional** a nivel de FastAPI (`DeleteAccountRequest | None = Body(default=None)`). Si falta el cuerpo, si es `null` o `{}`, o si `confirm` es `false` o `null`, responde 400 `CONFIRMATION_REQUIRED` ("Confirma que quieres eliminar tu cuenta. Esta acción es definitiva y no se puede deshacer.") y no toca nada. Un `confirm` de tipo inválido (por ejemplo `"si"`) sigue el 422 estándar.
3. Con `confirm: true`, en **una transacción**: `DELETE FROM users WHERE id = :user_id RETURNING id`. El `user_id` sale de la sesión; si el cuerpo trae otro `user_id`, se ignora (NFR-10). El `ON DELETE CASCADE` de la BD borra sesiones, tokens de verificación, consentimientos y todo lo que cuelgue del usuario. **No se borra tabla por tabla**: esa es la garantía que debe dar la BD (§3.4).
4. Si el `DELETE` no afecta ninguna fila (doble clic, carrera) → rollback y 401 `UNAUTHENTICATED`, con la cookie borrada.
5. Responde `204` sin cuerpo, con la cookie borrada y `no-store`, construyendo la respuesta igual que el logout.
6. Logs: `account_deleted` (y `session_closed` en el logout) **sin correo, sin `user_id` y sin ningún identificador**, para que la eliminación también sea real en los logs.
7. No se envía correo de despedida: tras borrar no queda la dirección y está fuera del alcance.

Consecuencias inmediatas:
- **Sesiones de otros dispositivos:** dejan de existir por el cascade, así que el guard les responde 401.
- **Enlaces de verificación pendientes:** su fila también se borra, así que `verify-email` responde 410.
- **Volver a iniciar sesión:** `login` responde 404 `ACCOUNT_NOT_FOUND`.
- **Reenvío del enlace:** `resend-verification` responde 202 sin enviar correo.
- **Registrarse de nuevo:** el mismo correo puede registrarse y obtiene un `id` nuevo, con un consentimiento nuevo y sin historial.

### 3.3 NFR-11: `no-store` en todas las respuestas autenticadas

`core/cache_control.py` define `NoStoreMiddleware`, un middleware **ASGI puro** (no `BaseHTTPMiddleware`, para no afectar el streaming ni las `BackgroundTasks`). En el mensaje `http.response.start` de toda respuesta bajo `/api/v1` fija `Cache-Control: no-store`, **incluidas las generadas por los manejadores de error** (400, 401, 403, 404, 422), que antes salían sin ese encabezado. Esto cierra el pendiente de la HU 2.

Excepciones (GET/HEAD públicos cacheables), configuradas en `main.py`: `/api/v1/programs` y `/api/v1/health`. `/health`, `/docs` y `/redoc` están fuera de `/api/v1` y no se tocan. Los 500 los emite `ServerErrorMiddleware`, que envuelve a todos los middlewares, por eso el manejador del 500 añade `no-store` directamente.

Los `no-store` que ya ponían el guard, `login` y `verify-email` se mantienen: son redundantes, pero así no cambia nada de lo que ya funcionaba.

### 3.4 Regla de cascada para las HU futuras (obligatoria)

Cada HU nueva (perfil, mediciones, rutinas elegidas, retos, puntos, ranking…) agregará tablas con datos del usuario. Para que eliminar una cuenta no deje restos nunca:

> **Regla:** toda tabla con datos de un usuario debe tener una columna `user_id` con `FOREIGN KEY … REFERENCES users(id) ON DELETE CASCADE` (directa, o colgar de otra tabla que a su vez tenga cascade hacia `users`). Toda FK que apunte a `users` debe ser `ON DELETE CASCADE`.

`tests/integration/test_schema_cascade.py` lo verifica contra la BD de pruebas real, ya migrada con Alembic:
- `test_toda_fk_hacia_users_es_on_delete_cascade`: toda FK con `confrelid = users` tiene `pg_constraint.confdeltype = 'c'`.
- `test_toda_tabla_con_user_id_cuelga_de_users_con_cascade`: toda tabla de `public` con columna `user_id` tiene una FK **sobre esa columna** hacia `users` con cascade.
- `test_la_verificacion_de_esquema_detecta_una_tabla_sin_cascade` (autochequeo): crea dentro de una transacción una tabla con FK sin cascade y otra con `user_id` sin FK, comprueba que ambas se detectan y revierte.

Excepciones: el diccionario `CASCADE_EXCEPTIONS` del test, **hoy vacío**. Cualquier entrada nueva necesita una justificación escrita y aprobarse en revisión. `ai_call_logs` no tendrá `user_id` por diseño (ADR-07: cero PII hacia la IA), así que no entra en la regla.

Así, una migración futura que olvide el cascade hace fallar el CI.

Límite de la regla: los datos de un usuario guardados en tablas **sin** `user_id` (por ejemplo, un id en un JSON o en texto libre) no los detecta este test. No se debe modelar así.

### 3.5 Regla del ranking para la Épica 6 (AC-3-5)

El ranking **no se implementa en esta HU**. AC-3-5 se cumple de forma **estructural**: al borrarse el usuario desaparecen en cascada sus filas de puntos, retos, etc. (garantizado por §3.4). Regla obligatoria para la Épica 6:

> El ranking debe calcularse desde las tablas vivas (JOIN con `users`), sin snapshots, vistas materializadas ni cachés. Si algún día se añade una caché, por rendimiento, **debe invalidarse en la misma operación de eliminar la cuenta**, y el test de AC-3-5 debe ampliarse para cubrirla.

En este release, AC-3-5 se valida así:
- a nivel de esquema (§3.4);
- con una lectura inmediata, desde otra conexión justo después del 204, que confirma que no queda ninguna fila del usuario.

**Pendiente:** completar la validación con el ranking real cuando exista la Épica 6, igual que el supuesto S-07 de la arquitectura.

### 3.6 Limitación conocida (S-13 / R-07): respaldos del proveedor

La eliminación es inmediata y definitiva en la base de datos operativa. Sin embargo, los **respaldos automáticos de Supabase** pueden conservar por un tiempo copias que contienen datos ya eliminados, hasta que esos respaldos rotan según la política de retención del plan contratado. Esos respaldos no son consultables desde la aplicación. Esta limitación debe constar en el aviso de privacidad (HU 8).

## 4. Cómo se hicieron las pruebas

Mismo enfoque que HU 1–2: pytest + pytest-asyncio + `httpx.AsyncClient` (`ASGITransport`) contra **Postgres real**, migraciones reales de Alembic y `dependency_overrides`. Cookies `Secure` enviadas a mano con `with_session(token)`.

**Fixtures nuevas**:
- `user_footprint(user_id)`: consulta `information_schema.columns` para encontrar **todas** las tablas con `user_id` (incluidas las de HU futuras, sin tocar el test) y devuelve `{tabla: filas}` junto con `users`. Es SQL dinámico, pero solo en pruebas y con nombres tomados del catálogo.
- `create_account()` (en `test_delete_account.py`): crea la cuenta **por la API** para que tenga un historial real:
  - registro, que deja el consentimiento y el token 1;
  - reenvío, que deja el token 2;
  - verificación, que crea la sesión 1;
  - dos logins, que crean las sesiones 2 y 3.

**Técnicas destacadas**:
- **Cookie reemitida en el logout:** se avanza el `FrozenClock` 11 min para que el guard reemita la cookie y se comprueba que la respuesta del logout lleva exactamente un `Set-Cookie`, el de borrado.
- **Doble clic:** dos `delete-account` simultáneos con `asyncio.gather`. El resultado es exactamente un 204 y un 401. Además, otro test simula con `monkeypatch` que el `DELETE` no afecta filas y comprueba el 401 con la cookie borrada.
- **Lectura inmediata (AC-3-5):** tras el 204, otra conexión a la BD comprueba que el usuario y todas sus filas ya no existen.
- **Mutaciones manuales de validación:**
  - Logout con el `Response` inyectado: el test de cookie viva falla.
  - Sin el middleware: fallan los casos 400, 403, 404 y 422 de `no-store`. Esto confirma que el hueco existía antes de esta HU.
- **NFR-03:** se mide el logout completo. La aserción es holgada (< 2 s); el tiempo se imprime con `-s` y se registra como `record_property`. Se midieron **18–24 ms**.
- **Logs:** se captura la salida del `JsonFormatter` y `caplog`, y se comprueba que no aparecen ni el correo ni el `user_id`.

**Resultados**: 192 pruebas (144 de HU 1–2 sin cambios + 48 nuevas) pasan en Python 3.14 local y en `python:3.11-slim` (Docker).

### Tabla AC → pruebas

| AC | Prueba(s) |
|---|---|
| AC-3-1 | `test_ac_3_1_cerrar_sesion_la_invalida_en_el_servidor`, `test_ac_3_1_token_guardado_antes_del_logout_ya_no_sirve`, `test_ac_3_1_solo_cierra_la_sesion_actual`, `test_ac_3_1_no_deja_cookie_viva_aunque_el_guard_la_reemita`, `test_ac_3_1_funciona_con_diagnostico_incompleto`, `test_ac_3_1_sin_sesion_devuelve_401`, `test_ac_3_1_sin_encabezado_csrf_devuelve_403` |
| AC-3-2 | `test_ac_3_2_confirmar_elimina_cuenta_datos_e_historial`, `test_ac_3_2_todas_las_sesiones_quedan_invalidas`, `test_ac_3_2_no_toca_los_datos_de_otro_usuario`, `test_ac_3_2_funciona_con_diagnostico_incompleto`, `test_ac_3_2_sin_sesion_devuelve_401`, `test_ac_3_2_sin_encabezado_csrf_devuelve_403_y_no_borra` |
| AC-3-3 | `test_ac_3_3_sin_confirmacion_la_cuenta_sigue_intacta` (sin cuerpo, `{}`, `confirm:false`, `confirm:null`, JSON `null`), `test_confirm_con_tipo_invalido_devuelve_422_y_no_borra` |
| AC-3-4 | `test_ac_3_4_login_de_cuenta_eliminada_es_rechazado`, `test_ac_3_4_reenvio_a_cuenta_eliminada_no_envia_correo`, `test_ac_3_4_enlace_de_verificacion_viejo_deja_de_servir`, `test_ac_3_4_sesion_de_otro_dispositivo_es_rechazada` |
| AC-3-5 | `test_ac_3_5_datos_no_consultables_inmediatamente_tras_eliminar` + los 3 tests de `test_schema_cascade.py` (validación con ranking real: **pendiente, Épica 6**) |
| AC-3-6 | `test_ac_3_6_registrarse_de_nuevo_crea_una_cuenta_nueva_desde_cero` |
| NFR-03 | `test_nfr_03_logout_responde_en_menos_de_2_segundos` |
| NFR-10 | `test_nfr_10_el_usuario_a_eliminar_sale_de_la_sesion_no_del_cuerpo` |
| NFR-11 | `test_nfr_11_respuestas_autenticadas_llevan_no_store` (10 casos: 200, 204, 400, 401, 403, 404, 422), `test_nfr_11_rutas_publicas_cacheables_no_se_ven_afectadas`, `test_nfr_11_mutaciones_publicas_tambien_son_no_store` |
| NFR-12 | `test_toda_fk_hacia_users_es_on_delete_cascade`, `test_toda_tabla_con_user_id_cuelga_de_users_con_cascade`, `test_la_verificacion_de_esquema_detecta_una_tabla_sin_cascade` |

Otras pruebas:
- **Carrera:** `test_doble_clic_elimina_una_vez_y_la_segunda_peticion_da_401` y `test_si_el_delete_no_afecta_filas_responde_401_y_borra_la_cookie`.
- **Logs:** `test_logs_de_logout_no_contienen_correo_ni_user_id` y `test_logs_de_eliminacion_no_contienen_correo_ni_user_id`.

## 5. Cómo probarlo manualmente

### 5.1 Levantar el entorno

Igual que en [H1.md §5.1](H1.md). Usa `.env` con `COOKIE_SECURE=false` y `MAIL_PROVIDER=console`, y el puerto 5433 si tienes otro Postgres en 5432.

```bash
POSTGRES_PORT=5433 docker compose up -d db
cd apps/api
.venv/bin/alembic upgrade head && .venv/bin/python -m seeds.load_academic_programs
.venv/bin/uvicorn app.main:app --reload --proxy-headers
```

### 5.2 Recorrido completo con curl

```bash
B=http://localhost:8000/api/v1
H=(-H "X-Requested-With: fitia" -H "Content-Type: application/json")
JAR=/tmp/fitia-cookies.txt; rm -f $JAR

# 1. Registro y verificación (copia el token del correo impreso por uvicorn)
curl -s "${H[@]}" $B/auth/register -d '{"nickname":"Pantera","email":"ana.gomez@correounivalle.edu.co",
  "password":"clave-antigua-1","program_code":"ING-SIS","accepted_terms":true}'
curl -s "${H[@]}" $B/auth/verify-email -d '{"token":"PEGA_EL_TOKEN"}'

# 2. Login y /me
curl -s -c $JAR "${H[@]}" $B/auth/login -d '{"email":"ana.gomez@correounivalle.edu.co","password":"clave-antigua-1"}'
OLD=$(grep fitia_session $JAR | awk '{print $7}')       # guarda el token "robado"
curl -s -b $JAR $B/me                                   # → 200

# 3. Logout (AC-3-1)
curl -s -i -b $JAR -c $JAR "${H[@]}" -X POST $B/auth/logout
# → 204, Set-Cookie: fitia_session=""; …; Max-Age=0; Path=/; SameSite=lax, Cache-Control: no-store

# 4. El token anterior ya no sirve (NFR-11)
curl -s -i -H "Cookie: fitia_session=$OLD" $B/me       # → 401 UNAUTHENTICATED

# 5. Login de nuevo
curl -s -c $JAR "${H[@]}" $B/auth/login -d '{"email":"ana.gomez@correounivalle.edu.co","password":"clave-antigua-1"}'

# 6. Eliminar SIN confirmar (AC-3-3) → 400 CONFIRMATION_REQUIRED, nada cambia
curl -s -b $JAR "${H[@]}" -X POST $B/me/delete-account
curl -s -b $JAR "${H[@]}" $B/me/delete-account -d '{"confirm":false}'

# 7. Eliminar confirmando (AC-3-2) → 204 + cookie borrada
curl -s -i -b $JAR -c $JAR "${H[@]}" $B/me/delete-account -d '{"confirm":true}'

# 8. Login tras eliminar (AC-3-4) → 404 ACCOUNT_NOT_FOUND
curl -s "${H[@]}" $B/auth/login -d '{"email":"ana.gomez@correounivalle.edu.co","password":"clave-antigua-1"}'

# 9. Registro de nuevo con el mismo correo (AC-3-6) → 201; verifica con el token nuevo
curl -s "${H[@]}" $B/auth/register -d '{"nickname":"Renacido","email":"  ANA.Gomez@CorreoUnivalle.edu.co ",
  "password":"clave-nueva-22","program_code":"MED","accepted_terms":true}'
curl -s "${H[@]}" $B/auth/verify-email -d '{"token":"PEGA_EL_TOKEN_NUEVO"}'
curl -s -c $JAR "${H[@]}" $B/auth/login -d '{"email":"ana.gomez@correounivalle.edu.co","password":"clave-nueva-22"}'  # 200
curl -s "${H[@]}" $B/auth/login -d '{"email":"ana.gomez@correounivalle.edu.co","password":"clave-antigua-1"}'         # 401
curl -s -b $JAR $B/me      # id nuevo, apodo "Renacido", onboarding_completed:false
```

### 5.3 Casos de error

| Qué probar | Petición | Esperado |
|---|---|---|
| Logout sin sesión | `curl -s -X POST "${H[@]}" $B/auth/logout` | 401 `UNAUTHENTICATED` |
| Logout sin CSRF | sin `X-Requested-With` | 403 `CSRF_HEADER_MISSING` |
| Eliminar sin sesión | `-d '{"confirm":true}'` sin cookie | 401 |
| `confirm` de tipo inválido | `-d '{"confirm":"si"}'` | 422 `VALIDATION_ERROR` (campo `confirm`) |
| Eliminar dos veces con la misma cookie | repetir el paso 7 | 401 |
| Logout en un dispositivo | dos logins (dos jars), logout en uno | el otro sigue con `/me` 200 |
| Eliminar en un dispositivo | dos logins, eliminar en uno | el otro recibe 401 |
| `no-store` en errores | `curl -s -i -b $JAR "${H[@]}" $B/me/delete-account -d '{}'` | 400 con `Cache-Control: no-store` |
| Rutas públicas cacheables | `curl -s -I $B/programs` | sin `Cache-Control` |

### 5.4 Revisar la BD con psql

```bash
docker exec -it fitia_postgres psql -U postgres -d fitia_db
```
```sql
-- Antes y después de eliminar: huella del usuario en todas las tablas con datos suyos
SELECT 'users' t, count(*) FROM users WHERE email = 'ana.gomez@correounivalle.edu.co'
UNION ALL SELECT 'sessions', count(*) FROM sessions s JOIN users u ON u.id = s.user_id
UNION ALL SELECT 'consents', count(*) FROM consents
UNION ALL SELECT 'tokens', count(*) FROM email_verification_tokens;

-- Sesiones tras el logout: la fila de la sesión cerrada ya no está
SELECT user_id, left(token_hash, 12), expires_at FROM sessions;

-- Regla de cascada: toda FK hacia users debe tener confdeltype = 'c'
SELECT conrelid::regclass AS tabla, conname, confdeltype
FROM pg_constraint WHERE contype = 'f' AND confrelid = 'users'::regclass;

-- Tablas con user_id (todas deben aparecer arriba con 'c')
SELECT table_name FROM information_schema.columns
WHERE table_schema = 'public' AND column_name = 'user_id';
```

### 5.5 Pruebas automáticas

```bash
cd apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/fitia_test .venv/bin/pytest -v
# Solo la HU 3:
TEST_DATABASE_URL=... .venv/bin/pytest -v tests/integration/test_logout.py tests/integration/test_delete_account.py \
  tests/integration/test_schema_cascade.py tests/integration/test_no_store.py
# Tiempo medido de NFR-03:
TEST_DATABASE_URL=... .venv/bin/pytest -s -k nfr_03
```

## 6. Supuestos tomados

1. **Logout solo de la sesión actual:** las de otros dispositivos siguen vivas. "Cerrar sesión en todos los dispositivos" está fuera de alcance.
2. **Eliminar exige solo sesión válida y `{"confirm": true}`:** no se pide reautenticación con contraseña (fuera de alcance). Una cookie robada permitiría eliminar la cuenta; lo mitigan `HttpOnly`, `SameSite=Lax`, el encabezado CSRF y que el logout invalida el token en el servidor.
3. **Confirmación con tipo inválido:** `confirm: "si"` (u otro tipo) responde 422 estándar, no 400. Solo la ausencia o un valor `false`/`null` responden 400.
4. **401 en vez de 404 cuando el `DELETE` no afecta filas:** la sesión ya no es válida, y así la SPA lo trata igual que cualquier sesión cerrada.
5. **Logs sin identificadores:** `session_closed` y `account_deleted` no llevan `user_id`. Se pierde trazabilidad por usuario de estos dos eventos a cambio de que la eliminación también sea real en los logs. Los logs **anteriores** a la eliminación (`login_succeeded`, `user_registered`…) sí contienen el `user_id` (no el correo) y se conservan según la retención de logs de Render; ese `user_id` ya no corresponde a ninguna fila.
6. **`no-store` en todo `/api/v1`, salvo `GET /programs` y `GET /api/v1/health`:** incluye las mutaciones públicas (registro, login…). No tiene costo y evita listas de rutas que mantener.
7. **Rate limit en memoria:** los contadores de intentos asociados al hash del correo eliminado se descartan solos al vencer la ventana (15 min); no se limpian al eliminar la cuenta.
8. **Respaldos de Supabase (S-13 / R-07):** pueden conservar datos eliminados hasta que rotan (§3.6).

## 7. Pendiente / fuera de alcance

- **Épica 6 (ranking):** completar AC-3-5 con el ranking real y respetar la regla de §3.5 (sin cachés, o invalidarlas al eliminar).
- **HU futuras:** cumplir la regla de cascada de §3.4. El CI lo verifica.
- **HU 8:** mencionar en el aviso de privacidad la retención en respaldos del proveedor (§3.6).
- **Frontend:**
  - botón "Cerrar sesión" que trate el 401 como sesión ya cerrada;
  - pantalla de confirmación de eliminación; "Cancelar" no envía ninguna petición, y "Eliminar" envía `{"confirm": true}`;
  - redirección a la bienvenida tras el 204.
- **Fuera de alcance:** cerrar sesión en todos los dispositivos, reautenticación para eliminar, período de gracia o papelera, correo de despedida, exportación de datos, recuperación de contraseña.
