"""HU 2 - Inicio de sesión: AC-2-1 a AC-2-6, NFR-02, NFR-08 y protecciones del login."""
import io
import logging
import time

import httpx
import pytest
from argon2 import PasswordHasher, Type
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import JsonFormatter
from app.core.security import hash_token, password_needs_rehash
from app.modules.auth import service as auth_service
from app.modules.auth.models import User, UserSession
from tests.conftest import PASSWORD, SeededUser, session_token, with_session
from tests.fakes import FakeMailer, FakeOnboardingStatus

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/me"
EMAIL = "ana.gomez@correounivalle.edu.co"


async def _session_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(UserSession)) or 0


def _field_codes(response: httpx.Response) -> dict[str, str]:
    return {f["field"]: f["code"] for f in response.json()["error"]["fields"]}


@pytest.fixture
def argon_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Registra cada verificación Argon2 que hace el login."""
    calls: list[str] = []
    original = auth_service.verify_password

    def _spy(password_hash: str, password: str) -> bool:
        calls.append(password_hash)
        return original(password_hash, password)

    monkeypatch.setattr(auth_service, "verify_password", _spy)
    return calls


# --- Criterios de aceptación -------------------------------------------------


async def test_ac_2_1_credenciales_correctas_inician_sesion_y_dan_acceso(
    client: httpx.AsyncClient, login, verified_user: SeededUser, onboarding: FakeOnboardingStatus
) -> None:
    onboarding.completed = True

    response = await login(verified_user.email)

    assert response.status_code == 200
    body = response.json()
    assert body["next"] == "home"
    assert body["user"] == {
        "id": str(verified_user.id),
        "nickname": "Pantera",
        "program": {"code": "ING-SIS", "name": "Ingeniería de Sistemas"},
    }
    assert response.headers["Cache-Control"] == "no-store"
    cookie = response.headers["set-cookie"].lower()
    for attribute in ("httponly", "samesite=lax", "path=/", "secure"):
        assert attribute in cookie

    me = await client.get(ME_URL, headers=with_session(session_token(response)))
    assert me.status_code == 200
    assert me.json()["id"] == str(verified_user.id)


async def test_ac_2_2_contrasena_incorrecta_no_inicia_sesion(
    login, verified_user: SeededUser, db: AsyncSession
) -> None:
    response = await login(verified_user.email, "contrasena-equivocada")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert "set-cookie" not in response.headers
    assert await _session_count(db) == 0


@pytest.mark.parametrize("email", ["nadie@correounivalle.edu.co", "ana.gomez@gmail.com"])
async def test_ac_2_3_correo_no_registrado_invita_a_registrarse(
    login, verified_user: SeededUser, argon_calls: list[str], email: str
) -> None:
    response = await login(email)

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "ACCOUNT_NOT_FOUND"
    assert "no está registrado" in error["message"]
    assert "Crea una cuenta" in error["message"]
    assert _field_codes(response) == {"email": "ACCOUNT_NOT_FOUND"}
    assert argon_calls == []


async def test_ac_2_4_sin_diagnostico_completo_lleva_a_onboarding(
    login, verified_user: SeededUser, onboarding: FakeOnboardingStatus
) -> None:
    onboarding.completed = False

    response = await login(verified_user.email)

    assert response.status_code == 200
    assert response.json()["next"] == "onboarding"


async def test_ac_2_4_por_defecto_el_diagnostico_se_considera_incompleto(
    client: httpx.AsyncClient, login, verified_user: SeededUser
) -> None:
    # Sin override: se usa PendingOnboardingStatus hasta que exista la HU 4.
    response = await login(verified_user.email)

    assert response.json()["next"] == "onboarding"
    me = await client.get(ME_URL, headers=with_session(session_token(response)))
    assert me.json()["onboarding_completed"] is False


async def test_ac_2_6_cuenta_sin_verificar_no_inicia_sesion(
    login, pending_user: SeededUser, db: AsyncSession
) -> None:
    response = await login(pending_user.email)

    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "EMAIL_NOT_VERIFIED"
    assert "verificar tu correo" in error["message"]
    assert "set-cookie" not in response.headers
    assert await _session_count(db) == 0


async def test_ac_2_6_cuenta_sin_verificar_con_contrasena_incorrecta_no_revela_su_estado(
    login, pending_user: SeededUser
) -> None:
    response = await login(pending_user.email, "contrasena-equivocada")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_ac_2_6_flujo_completo_pendiente_verificar_y_luego_iniciar_sesion(
    client: httpx.AsyncClient, register, login, mailer: FakeMailer
) -> None:
    assert (await register(password=PASSWORD)).status_code == 201
    assert (await login(EMAIL)).status_code == 403

    resend = await client.post("/api/v1/auth/resend-verification", json={"email": EMAIL})
    assert resend.status_code == 202
    verify = await client.post("/api/v1/auth/verify-email", json={"token": mailer.last_token()})
    assert verify.status_code == 200

    assert (await login(EMAIL)).status_code == 200


# --- Normalización y validación ----------------------------------------------


async def test_correo_con_espacios_y_mayusculas_inicia_sesion(login, verified_user: SeededUser) -> None:
    response = await login("   Ana.GOMEZ@CorreoUnivalle.EDU.CO  ")

    assert response.status_code == 200


async def test_cuerpo_vacio_devuelve_todos_los_campos(client: httpx.AsyncClient) -> None:
    response = await client.post(LOGIN_URL, json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _field_codes(response) == {"email": "INVALID_EMAIL", "password": "REQUIRED"}


@pytest.mark.parametrize("email", ["sin-arroba", "a@b@correounivalle.edu.co", "   "])
async def test_correo_mal_formado_es_invalid_email(login, email: str) -> None:
    response = await login(email)

    assert response.status_code == 422
    assert _field_codes(response) == {"email": "INVALID_EMAIL"}


async def test_contrasena_mayor_a_128_es_password_too_long(login, argon_calls: list[str]) -> None:
    response = await login(EMAIL, "x" * 129)

    assert response.status_code == 422
    assert _field_codes(response) == {"password": "PASSWORD_TOO_LONG"}
    assert argon_calls == []


async def test_login_no_aplica_minimo_de_8_caracteres(make_user, login) -> None:
    # Una contraseña corta incorrecta es un fallo de credenciales, no de validación.
    await make_user()

    response = await login(EMAIL, "corta")

    assert response.status_code == 401


# --- Seguridad ---------------------------------------------------------------


async def test_sin_encabezado_x_requested_with_devuelve_403(client: httpx.AsyncClient, verified_user) -> None:
    response = await client.post(
        LOGIN_URL, json={"email": EMAIL, "password": PASSWORD}, headers={"X-Requested-With": ""}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_HEADER_MISSING"


async def test_respuestas_no_contienen_correo_ni_hashes(
    client: httpx.AsyncClient, login, verified_user: SeededUser, db: AsyncSession
) -> None:
    response = await login(verified_user.email)
    me = await client.get(ME_URL, headers=with_session(session_token(response)))

    password_hash = await db.scalar(select(User.password_hash))
    token_hash = await db.scalar(select(UserSession.token_hash))
    for text in (response.text, me.text):
        assert verified_user.email not in text
        assert "$argon2" not in text
        assert str(password_hash) not in text
        assert str(token_hash) not in text


async def test_token_de_sesion_se_guarda_solo_como_hash(
    login, verified_user: SeededUser, db: AsyncSession
) -> None:
    token = session_token(await login(verified_user.email))

    stored = (await db.scalars(select(UserSession.token_hash))).all()
    assert stored == [hash_token(token)]


async def test_cada_login_crea_una_sesion_distinta_y_ambas_conviven(
    client: httpx.AsyncClient, login, verified_user: SeededUser, db: AsyncSession
) -> None:
    first = session_token(await login(verified_user.email))
    second = session_token(await login(verified_user.email))

    assert first != second
    assert await _session_count(db) == 2
    assert (await client.get(ME_URL, headers=with_session(first))).status_code == 200
    assert (await client.get(ME_URL, headers=with_session(second))).status_code == 200


async def test_login_con_cookie_previa_no_reutiliza_la_sesion(
    client: httpx.AsyncClient, login, verified_user: SeededUser
) -> None:
    previous = session_token(await login(verified_user.email))

    response = await client.post(
        LOGIN_URL, json={"email": verified_user.email, "password": PASSWORD}, headers=with_session(previous)
    )

    assert session_token(response) != previous


# --- Rate limit ----------------------------------------------------------------


async def test_rate_limit_por_correo_tras_intentos_fallidos(
    login, verified_user: SeededUser, argon_calls: list[str]
) -> None:
    for _ in range(5):
        assert (await login(verified_user.email, "mala-clave")).status_code == 401
    calls_before = len(argon_calls)

    response = await login(verified_user.email, PASSWORD)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert int(response.headers["Retry-After"]) > 0
    assert len(argon_calls) == calls_before, "el 429 debe llegar sin ejecutar Argon2"


async def test_login_exitoso_reinicia_el_contador_de_fallos(login, verified_user: SeededUser) -> None:
    for _ in range(4):
        await login(verified_user.email, "mala-clave")
    assert (await login(verified_user.email)).status_code == 200

    statuses = [(await login(verified_user.email, "mala-clave")).status_code for _ in range(6)]

    assert statuses == [401] * 5 + [429]


async def test_logins_exitosos_no_cuentan_para_el_limite_por_correo(login, verified_user: SeededUser) -> None:
    statuses = [(await login(verified_user.email)).status_code for _ in range(7)]

    assert statuses == [200] * 7


async def test_correos_inexistentes_tambien_cuentan_como_fallo(login) -> None:
    statuses = [(await login("nadie@correounivalle.edu.co")).status_code for _ in range(6)]

    assert statuses == [404] * 5 + [429]


async def test_rate_limit_por_ip_cuenta_todos_los_intentos(client: httpx.AsyncClient, login, settings) -> None:
    settings.RATE_LIMIT_LOGIN_PER_IP = 3
    for i in range(3):
        await login(f"u{i}@correounivalle.edu.co")

    response = await login("otro@correounivalle.edu.co")

    assert response.status_code == 429
    assert "Retry-After" in response.headers


# --- NFR-08: rehash ------------------------------------------------------------


async def test_hash_con_parametros_antiguos_se_actualiza_tras_login(
    make_user, login, db: AsyncSession
) -> None:
    legacy_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1, type=Type.ID).hash(PASSWORD)
    assert password_needs_rehash(legacy_hash)
    await make_user(password_hash=legacy_hash)

    assert (await login(EMAIL)).status_code == 200

    new_hash = await db.scalar(select(User.password_hash))
    assert new_hash is not None and new_hash != legacy_hash
    assert new_hash.startswith("$argon2id$")
    assert not password_needs_rehash(new_hash)
    assert (await login(EMAIL)).status_code == 200


# --- Logs sin PII --------------------------------------------------------------


async def test_logs_de_login_fallido_no_contienen_correo_ni_contrasena(
    login, verified_user: SeededUser, caplog: pytest.LogCaptureFixture
) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("fitia")
    logger.addHandler(handler)
    caplog.set_level(logging.DEBUG)
    try:
        await login(verified_user.email, "clave-secreta-erronea")
        await login("nadie@correounivalle.edu.co", "otra-clave-secreta")
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue() + caplog.text
    assert "login_failed" in output
    for secret in (verified_user.email, "nadie@correounivalle.edu.co", "clave-secreta-erronea", "otra-clave-secreta"):
        assert secret not in output


# --- NFR-02: tiempo de respuesta ------------------------------------------------


async def test_nfr_02_login_completo_responde_en_menos_de_3_segundos(
    login, verified_user: SeededUser, record_property
) -> None:
    started = time.perf_counter()
    response = await login(verified_user.email)
    elapsed = time.perf_counter() - started

    record_property("login_seconds", round(elapsed, 3))
    print(f"\n[NFR-02] login completo (Argon2id incluido): {elapsed * 1000:.0f} ms")
    assert response.status_code == 200
    assert elapsed < 3.0
