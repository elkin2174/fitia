"""HU 3 - Cerrar sesión: AC-3-1, NFR-03 y NFR-11."""
import io
import logging
import time
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import FrozenClock
from app.core.logging import JsonFormatter
from app.core.security import hash_token
from app.modules.auth.models import UserSession
from tests.conftest import SeededUser, session_token, with_session
from tests.fakes import FakeOnboardingStatus

LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/me"


@pytest.fixture
async def token(login, verified_user: SeededUser) -> str:
    return session_token(await login(verified_user.email))


def assert_session_cookie_deleted(response: httpx.Response) -> None:
    """Exactamente un Set-Cookie, y es el de borrado con los mismos atributos con que se fijó."""
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 1, f"se esperaba solo la cookie de borrado: {cookies}"
    cookie = cookies[0].lower()
    assert cookie.startswith('fitia_session="";')
    for attribute in ("max-age=0", "path=/", "samesite=lax", "httponly", "secure"):
        assert attribute in cookie


async def _session_exists(db: AsyncSession, token: str) -> bool:
    count = await db.scalar(
        select(func.count()).select_from(UserSession).where(UserSession.token_hash == hash_token(token))
    )
    return bool(count)


async def test_ac_3_1_cerrar_sesion_la_invalida_en_el_servidor(
    client: httpx.AsyncClient, token: str, db: AsyncSession
) -> None:
    assert await _session_exists(db, token)

    response = await client.post(LOGOUT_URL, headers=with_session(token))

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["Cache-Control"] == "no-store"
    assert_session_cookie_deleted(response)
    assert not await _session_exists(db, token)


async def test_ac_3_1_token_guardado_antes_del_logout_ya_no_sirve(client: httpx.AsyncClient, token: str) -> None:
    # Simula una cookie robada o volver atrás en el navegador después de cerrar sesión.
    await client.post(LOGOUT_URL, headers=with_session(token))

    response = await client.get(ME_URL, headers=with_session(token))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers["Cache-Control"] == "no-store"


async def test_ac_3_1_solo_cierra_la_sesion_actual(
    client: httpx.AsyncClient, login, verified_user: SeededUser, db: AsyncSession
) -> None:
    laptop = session_token(await login(verified_user.email))
    phone = session_token(await login(verified_user.email))

    await client.post(LOGOUT_URL, headers=with_session(laptop))

    assert (await client.get(ME_URL, headers=with_session(phone))).status_code == 200
    assert await _session_exists(db, phone)


async def test_ac_3_1_no_deja_cookie_viva_aunque_el_guard_la_reemita(
    client: httpx.AsyncClient, token: str, clock: FrozenClock
) -> None:
    # Pasado el intervalo, get_current_session reemite la cookie (expiración deslizante).
    clock.advance(timedelta(minutes=11))
    touched = await client.get(ME_URL, headers=with_session(token))
    assert session_token(touched) == token
    clock.advance(timedelta(minutes=11))

    response = await client.post(LOGOUT_URL, headers=with_session(token))

    assert response.status_code == 204
    assert_session_cookie_deleted(response)
    assert token not in response.headers["set-cookie"]


async def test_ac_3_1_funciona_con_diagnostico_incompleto(
    client: httpx.AsyncClient, token: str, onboarding: FakeOnboardingStatus
) -> None:
    onboarding.completed = False

    assert (await client.post(LOGOUT_URL, headers=with_session(token))).status_code == 204


async def test_ac_3_1_sin_sesion_devuelve_401(client: httpx.AsyncClient) -> None:
    response = await client.post(LOGOUT_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_ac_3_1_sin_encabezado_csrf_devuelve_403(
    client: httpx.AsyncClient, token: str, db: AsyncSession
) -> None:
    response = await client.post(LOGOUT_URL, headers={**with_session(token), "X-Requested-With": ""})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_HEADER_MISSING"
    assert await _session_exists(db, token)


async def test_nfr_03_logout_responde_en_menos_de_2_segundos(
    client: httpx.AsyncClient, token: str, record_property
) -> None:
    started = time.perf_counter()
    response = await client.post(LOGOUT_URL, headers=with_session(token))
    elapsed = time.perf_counter() - started

    record_property("logout_seconds", round(elapsed, 3))
    print(f"\n[NFR-03] logout completo: {elapsed * 1000:.0f} ms")
    assert response.status_code == 204
    assert elapsed < 2.0


async def test_logs_de_logout_no_contienen_correo_ni_user_id(
    client: httpx.AsyncClient, token: str, verified_user: SeededUser, caplog: pytest.LogCaptureFixture
) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("fitia")
    logger.addHandler(handler)
    caplog.set_level(logging.DEBUG)
    try:
        await client.post(LOGOUT_URL, headers=with_session(token))
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue() + caplog.text
    assert "session_closed" in output
    assert verified_user.email not in output
    assert str(verified_user.id) not in output
