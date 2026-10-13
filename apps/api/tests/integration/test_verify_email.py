"""HU 1 - Verificación por enlace: AC-1-7, AC-1-8 y NFR-09."""
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import FrozenClock
from app.core.security import hash_token
from app.modules.auth.models import User, UserSession
from tests.fakes import FakeMailer

VERIFY_URL = "/api/v1/auth/verify-email"
EMAIL = "ana.gomez@correounivalle.edu.co"


async def _registered_token(register, mailer: FakeMailer) -> str:
    assert (await register()).status_code == 201
    return mailer.last_token()


async def test_ac_1_7_enlace_valido_verifica_la_cuenta_y_lleva_al_diagnostico(
    client: httpx.AsyncClient, register, mailer: FakeMailer, db: AsyncSession, clock: FrozenClock
) -> None:
    token = await _registered_token(register, mailer)

    response = await client.post(VERIFY_URL, json={"token": token})

    assert response.status_code == 200
    body = response.json()
    assert body["next"] == "onboarding"
    assert body["user"]["nickname"] == "Pantera"
    assert body["user"]["program"] == {"code": "ING-SIS", "name": "Ingeniería de Sistemas"}
    assert set(body["user"]) == {"id", "nickname", "program"}
    assert EMAIL not in response.text
    assert response.headers["Cache-Control"] == "no-store"

    user = await db.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    assert str(user.id) == body["user"]["id"]
    assert user.email_verified_at == clock.now()


async def test_ac_1_7_verificacion_crea_sesion_con_cookie_segura(
    client: httpx.AsyncClient, register, mailer: FakeMailer, db: AsyncSession, clock: FrozenClock
) -> None:
    token = await _registered_token(register, mailer)

    response = await client.post(VERIFY_URL, json={"token": token})

    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith("fitia_session=")
    for attribute in ("HttpOnly", "Secure", "SameSite=lax", "Path=/", "Max-Age=2592000"):
        assert attribute.lower() in set_cookie.lower()

    session_token = set_cookie.split(";", 1)[0].split("=", 1)[1]
    stored = await db.scalar(select(UserSession))
    assert stored is not None
    assert stored.token_hash == hash_token(session_token)
    assert stored.expires_at == clock.now() + timedelta(days=30)


async def test_ac_1_8_enlace_vencido_informa_y_permite_pedir_uno_nuevo(
    client: httpx.AsyncClient, register, mailer: FakeMailer, db: AsyncSession, clock: FrozenClock
) -> None:
    token = await _registered_token(register, mailer)
    clock.advance(timedelta(hours=24, seconds=1))

    response = await client.post(VERIFY_URL, json={"token": token})

    assert response.status_code == 410
    error = response.json()["error"]
    assert error["code"] == "TOKEN_EXPIRED_OR_USED"
    assert "Solicita uno nuevo" in error["message"]
    assert "set-cookie" not in response.headers
    assert await db.scalar(select(User.email_verified_at)) is None

    resend = await client.post("/api/v1/auth/resend-verification", json={"email": EMAIL})
    assert resend.status_code == 202
    retry = await client.post(VERIFY_URL, json={"token": mailer.last_token()})
    assert retry.status_code == 200


async def test_ac_1_8_enlace_ya_usado_no_sirve_dos_veces(
    client: httpx.AsyncClient, register, mailer: FakeMailer
) -> None:
    token = await _registered_token(register, mailer)

    first = await client.post(VERIFY_URL, json={"token": token})
    second = await client.post(VERIFY_URL, json={"token": token})

    assert first.status_code == 200
    assert second.status_code == 410
    assert second.json()["error"]["code"] == "TOKEN_EXPIRED_OR_USED"


async def test_enlace_sigue_vigente_un_segundo_antes_de_las_24_horas(
    client: httpx.AsyncClient, register, mailer: FakeMailer, clock: FrozenClock
) -> None:
    token = await _registered_token(register, mailer)
    clock.advance(timedelta(hours=24) - timedelta(seconds=1))

    response = await client.post(VERIFY_URL, json={"token": token})

    assert response.status_code == 200


async def test_token_inexistente_devuelve_410(client: httpx.AsyncClient) -> None:
    response = await client.post(VERIFY_URL, json={"token": "token-que-no-existe"})

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED_OR_USED"


async def test_verificacion_sin_encabezado_csrf_devuelve_403(client: httpx.AsyncClient) -> None:
    response = await client.post(VERIFY_URL, json={"token": "x"}, headers={"X-Requested-With": "otro"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_HEADER_MISSING"
