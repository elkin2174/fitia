"""HU 2 - Guards de sesión: AC-2-5, NFR-10, NFR-11 (parcial) y expiración deslizante."""
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import FrozenClock
from app.modules.auth.models import User, UserSession
from tests.conftest import SeededUser, session_token, with_session
from tests.fakes import FakeOnboardingStatus

ME_URL = "/api/v1/me"


@pytest.fixture
async def token(login, verified_user: SeededUser) -> str:
    return session_token(await login(verified_user.email))


def _assert_cookie_cleared(response: httpx.Response) -> None:
    cookie = response.headers["set-cookie"]
    assert cookie.startswith('fitia_session=""') or cookie.startswith("fitia_session=;")
    assert "max-age=0" in cookie.lower()


# --- AC-2-5: sin sesión → 401 ----------------------------------------------------


async def test_ac_2_5_me_sin_cookie_devuelve_401(client: httpx.AsyncClient) -> None:
    response = await client.get(ME_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers["Cache-Control"] == "no-store"


async def test_ac_2_5_cookie_inventada_devuelve_401_y_borra_la_cookie(client: httpx.AsyncClient) -> None:
    response = await client.get(ME_URL, headers=with_session("token-inventado"))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    _assert_cookie_cleared(response)


async def test_ac_2_5_sesion_vencida_devuelve_401(
    client: httpx.AsyncClient, token: str, clock: FrozenClock
) -> None:
    clock.advance(timedelta(days=30, seconds=1))

    response = await client.get(ME_URL, headers=with_session(token))

    assert response.status_code == 401
    _assert_cookie_cleared(response)


async def test_ac_2_5_usuario_eliminado_invalida_la_sesion(
    client: httpx.AsyncClient, token: str, db: AsyncSession
) -> None:
    await db.execute(delete(User))
    await db.commit()

    assert (await client.get(ME_URL, headers=with_session(token))).status_code == 401


async def test_ac_2_5_usuario_no_verificado_con_sesion_devuelve_401(
    client: httpx.AsyncClient, token: str, db: AsyncSession
) -> None:
    await db.execute(User.__table__.update().values(email_verified_at=None))
    await db.commit()

    assert (await client.get(ME_URL, headers=with_session(token))).status_code == 401


async def test_ac_2_5_guard_de_perfil_exige_diagnostico_completo(
    client: httpx.AsyncClient, token: str, protected_route: str, onboarding: FakeOnboardingStatus
) -> None:
    onboarding.completed = False
    incomplete = await client.get(protected_route, headers=with_session(token))

    onboarding.completed = True
    complete = await client.get(protected_route, headers=with_session(token))

    assert incomplete.status_code == 403
    assert incomplete.json()["error"]["code"] == "ONBOARDING_REQUIRED"
    assert complete.status_code == 200
    assert complete.headers["Cache-Control"] == "no-store"


async def test_ac_2_5_guard_de_perfil_sin_sesion_devuelve_401(
    client: httpx.AsyncClient, protected_route: str
) -> None:
    assert (await client.get(protected_route)).status_code == 401


# --- /me ---------------------------------------------------------------------


async def test_me_devuelve_datos_de_la_sesion_sin_correo(
    client: httpx.AsyncClient, token: str, verified_user: SeededUser, onboarding: FakeOnboardingStatus
) -> None:
    onboarding.completed = True

    response = await client.get(ME_URL, headers=with_session(token))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(verified_user.id),
        "nickname": "Pantera",
        "program": {"code": "ING-SIS", "name": "Ingeniería de Sistemas"},
        "onboarding_completed": True,
    }
    assert response.headers["Cache-Control"] == "no-store"
    assert verified_user.email not in response.text


async def test_me_no_exige_encabezado_csrf(client: httpx.AsyncClient, token: str) -> None:
    response = await client.get(ME_URL, headers={**with_session(token), "X-Requested-With": ""})

    assert response.status_code == 200


async def test_nfr_10_me_ignora_ids_en_query(
    client: httpx.AsyncClient, token: str, verified_user: SeededUser, make_user
) -> None:
    other = await make_user("otro@correounivalle.edu.co", nickname="Otro")

    response = await client.get(ME_URL, params={"id": str(other.id), "user_id": str(other.id)}, headers=with_session(token))

    assert response.json()["id"] == str(verified_user.id)


# --- Expiración deslizante -------------------------------------------------------


async def test_peticion_dentro_del_intervalo_no_escribe_en_bd(
    client: httpx.AsyncClient, token: str, clock: FrozenClock, db: AsyncSession
) -> None:
    before = (await db.execute(select(UserSession.last_seen_at, UserSession.expires_at))).one()
    clock.advance(timedelta(minutes=9))

    response = await client.get(ME_URL, headers=with_session(token))

    after = (await db.execute(select(UserSession.last_seen_at, UserSession.expires_at))).one()
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert tuple(after) == tuple(before)


async def test_pasado_el_intervalo_extiende_la_sesion_y_renueva_la_cookie(
    client: httpx.AsyncClient, token: str, clock: FrozenClock, db: AsyncSession
) -> None:
    clock.advance(timedelta(minutes=10))

    response = await client.get(ME_URL, headers=with_session(token))

    row = (await db.execute(select(UserSession.last_seen_at, UserSession.expires_at))).one()
    assert response.status_code == 200
    assert row.last_seen_at == clock.now()
    assert row.expires_at == clock.now() + timedelta(days=30)
    assert session_token(response) == token  # mismo token, nueva expiración en el navegador


async def test_sesion_activa_sobrevive_mas_de_30_dias_desde_el_login(
    client: httpx.AsyncClient, token: str, clock: FrozenClock
) -> None:
    for _ in range(3):
        clock.advance(timedelta(days=20))
        assert (await client.get(ME_URL, headers=with_session(token))).status_code == 200
