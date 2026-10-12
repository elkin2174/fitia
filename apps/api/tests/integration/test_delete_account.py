"""HU 3 - Eliminar cuenta: AC-3-2 a AC-3-6, NFR-10 y NFR-12."""
import asyncio
import io
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import FrozenClock
from app.core.logging import JsonFormatter
from app.core.security import generate_token, hash_token
from app.modules.auth.models import Consent, EmailVerificationToken, User
from app.modules.auth.repository import AuthRepository
from tests.conftest import PASSWORD, session_token, with_session
from tests.fakes import FakeMailer, FakeOnboardingStatus
from tests.integration.test_logout import assert_session_cookie_deleted

DELETE_URL = "/api/v1/me/delete-account"
ME_URL = "/api/v1/me"
VERIFY_URL = "/api/v1/auth/verify-email"
RESEND_URL = "/api/v1/auth/resend-verification"
EMAIL = "ana.gomez@correounivalle.edu.co"
OTHER_EMAIL = "otro.estudiante@correounivalle.edu.co"


@dataclass(frozen=True)
class Account:
    id: uuid.UUID
    email: str
    password: str
    sessions: list[str]
    first_verification_token: str


@pytest.fixture
def create_account(client: httpx.AsyncClient, register, login, mailer: FakeMailer):
    """Cuenta creada por la API, con historial real: consentimiento, 2 tokens y 3 sesiones."""

    async def _create(email: str = EMAIL, nickname: str = "Pantera", password: str = PASSWORD) -> Account:
        assert (await register(email=email, nickname=nickname, password=password)).status_code == 201
        first_token = mailer.last_token()
        assert (await client.post(RESEND_URL, json={"email": email})).status_code == 202
        verify = await client.post(VERIFY_URL, json={"token": mailer.last_token()})
        assert verify.status_code == 200
        sessions = [session_token(verify)]
        for _ in range(2):
            sessions.append(session_token(await login(email, password)))
        return Account(
            id=uuid.UUID(verify.json()["user"]["id"]),
            email=email,
            password=password,
            sessions=sessions,
            first_verification_token=first_token,
        )

    return _create


async def _delete(client: httpx.AsyncClient, token: str, **kwargs) -> httpx.Response:
    return await client.post(DELETE_URL, headers=with_session(token), **kwargs)


# --- AC-3-2: confirmar elimina todo ---------------------------------------------


async def test_ac_3_2_confirmar_elimina_cuenta_datos_e_historial(
    client: httpx.AsyncClient, create_account, user_footprint
) -> None:
    account = await create_account()
    before = await user_footprint(account.id)
    assert before == {"users": 1, "consents": 1, "email_verification_tokens": 2, "sessions": 3}

    response = await _delete(client, account.sessions[0], json={"confirm": True})

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["Cache-Control"] == "no-store"
    assert_session_cookie_deleted(response)
    assert await user_footprint(account.id) == {table: 0 for table in before}


async def test_ac_3_2_todas_las_sesiones_quedan_invalidas(client: httpx.AsyncClient, create_account) -> None:
    account = await create_account()

    await _delete(client, account.sessions[0], json={"confirm": True})

    for token in account.sessions:  # la usada y las de "otros dispositivos"
        response = await client.get(ME_URL, headers=with_session(token))
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_ac_3_2_no_toca_los_datos_de_otro_usuario(
    client: httpx.AsyncClient, create_account, user_footprint
) -> None:
    account = await create_account()
    other = await create_account(OTHER_EMAIL, nickname="Vecino")
    other_before = await user_footprint(other.id)

    await _delete(client, account.sessions[0], json={"confirm": True})

    assert await user_footprint(other.id) == other_before
    assert (await client.get(ME_URL, headers=with_session(other.sessions[0]))).status_code == 200


async def test_ac_3_2_funciona_con_diagnostico_incompleto(
    client: httpx.AsyncClient, create_account, onboarding: FakeOnboardingStatus
) -> None:
    onboarding.completed = False
    account = await create_account()

    assert (await _delete(client, account.sessions[0], json={"confirm": True})).status_code == 204


async def test_ac_3_2_sin_sesion_devuelve_401(client: httpx.AsyncClient) -> None:
    response = await client.post(DELETE_URL, json={"confirm": True})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_ac_3_2_sin_encabezado_csrf_devuelve_403_y_no_borra(
    client: httpx.AsyncClient, create_account, user_footprint
) -> None:
    account = await create_account()

    response = await client.post(
        DELETE_URL, json={"confirm": True}, headers={**with_session(account.sessions[0]), "X-Requested-With": ""}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_HEADER_MISSING"
    assert (await user_footprint(account.id))["users"] == 1


async def test_nfr_10_el_usuario_a_eliminar_sale_de_la_sesion_no_del_cuerpo(
    client: httpx.AsyncClient, create_account, user_footprint
) -> None:
    account = await create_account()
    other = await create_account(OTHER_EMAIL, nickname="Vecino")

    response = await _delete(client, account.sessions[0], json={"confirm": True, "user_id": str(other.id)})

    assert response.status_code == 204
    assert (await user_footprint(account.id))["users"] == 0
    assert (await user_footprint(other.id))["users"] == 1


# --- AC-3-3: sin confirmación no se toca nada --------------------------------------
# En la interfaz, "Cancelar" en la pantalla de confirmación no genera ninguna petición: la cuenta
# queda intacta porque el backend nunca recibe nada. Aquí se cubre la petición sin confirmación.


@pytest.mark.parametrize(
    "body",
    [
        {},  # sin cuerpo
        {"json": {}},
        {"json": {"confirm": False}},
        {"json": {"confirm": None}},
        {"content": b"null", "headers_extra": {"Content-Type": "application/json"}},
    ],
    ids=["sin-cuerpo", "objeto-vacio", "confirm-false", "confirm-null", "json-null"],
)
async def test_ac_3_3_sin_confirmacion_la_cuenta_sigue_intacta(
    client: httpx.AsyncClient, create_account, user_footprint, body: dict
) -> None:
    account = await create_account()
    before = await user_footprint(account.id)
    token = account.sessions[0]
    extra = body.pop("headers_extra", {})

    response = await client.post(DELETE_URL, headers={**with_session(token), **extra}, **body)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "CONFIRMATION_REQUIRED"
    assert "Confirma" in error["message"]
    assert response.headers["Cache-Control"] == "no-store"
    assert await user_footprint(account.id) == before
    assert (await client.get(ME_URL, headers=with_session(token))).status_code == 200


async def test_confirm_con_tipo_invalido_devuelve_422_y_no_borra(
    client: httpx.AsyncClient, create_account, user_footprint
) -> None:
    account = await create_account()

    response = await _delete(client, account.sessions[0], json={"confirm": "si"})

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == [{"field": "confirm", "code": "INVALID"}]
    assert (await user_footprint(account.id))["users"] == 1


# --- AC-3-4: la cuenta eliminada es rechazada ---------------------------------------


async def test_ac_3_4_login_de_cuenta_eliminada_es_rechazado(client: httpx.AsyncClient, create_account, login) -> None:
    account = await create_account()
    await _delete(client, account.sessions[0], json={"confirm": True})

    response = await login(account.email, account.password)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


async def test_ac_3_4_reenvio_a_cuenta_eliminada_no_envia_correo(
    client: httpx.AsyncClient, create_account, mailer: FakeMailer
) -> None:
    account = await create_account()
    await _delete(client, account.sessions[0], json={"confirm": True})
    mailer.sent.clear()

    response = await client.post(RESEND_URL, json={"email": account.email})

    assert response.status_code == 202
    assert mailer.sent == []


async def test_ac_3_4_enlace_de_verificacion_viejo_deja_de_servir(
    client: httpx.AsyncClient, create_account, db: AsyncSession, clock: FrozenClock
) -> None:
    account = await create_account()
    # Enlace todavía vigente y sin usar (p. ej. un correo viejo en la bandeja).
    old_link = generate_token()
    db.add(
        EmailVerificationToken(
            user_id=account.id, token_hash=hash_token(old_link), expires_at=clock.now() + timedelta(hours=1)
        )
    )
    await db.commit()

    await _delete(client, account.sessions[0], json={"confirm": True})
    response = await client.post(VERIFY_URL, json={"token": old_link})

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED_OR_USED"
    assert "set-cookie" not in response.headers


async def test_ac_3_4_sesion_de_otro_dispositivo_es_rechazada(client: httpx.AsyncClient, create_account) -> None:
    account = await create_account()

    await _delete(client, account.sessions[0], json={"confirm": True})

    assert (await client.get(ME_URL, headers=with_session(account.sessions[2]))).status_code == 401
    logout = await client.post("/api/v1/auth/logout", headers=with_session(account.sessions[1]))
    assert logout.status_code == 401


# --- AC-3-5: no consultable de inmediato (ranking en la Épica 6) ----------------------


async def test_ac_3_5_datos_no_consultables_inmediatamente_tras_eliminar(
    client: httpx.AsyncClient, create_account, db: AsyncSession, user_footprint
) -> None:
    account = await create_account()

    response = await _delete(client, account.sessions[0], json={"confirm": True})

    # Lectura inmediata desde otra conexión, justo después del 204: no hay ventana de consistencia.
    assert response.status_code == 204
    assert await db.scalar(select(User).where(User.email == account.email)) is None
    assert all(count == 0 for count in (await user_footprint(account.id)).values())


# --- AC-3-6: el mismo correo puede registrarse de nuevo desde cero --------------------


async def test_ac_3_6_registrarse_de_nuevo_crea_una_cuenta_nueva_desde_cero(
    client: httpx.AsyncClient,
    create_account,
    register,
    login,
    mailer: FakeMailer,
    db: AsyncSession,
    user_footprint,
) -> None:
    old = await create_account(password="clave-antigua-1")
    assert (await _delete(client, old.sessions[0], json={"confirm": True})).status_code == 204

    again = await register(email="  ANA.Gomez@CorreoUnivalle.edu.co ", nickname="Renacido", password="clave-nueva-22")
    assert again.status_code == 201
    verify = await client.post(VERIFY_URL, json={"token": mailer.last_token()})
    assert verify.status_code == 200
    new_id = uuid.UUID(verify.json()["user"]["id"])

    assert new_id != old.id
    assert await user_footprint(new_id) == {
        "users": 1,
        "consents": 1,
        "email_verification_tokens": 1,
        "sessions": 1,
    }
    assert await db.scalar(select(func.count()).select_from(Consent)) == 1
    assert all(count == 0 for count in (await user_footprint(old.id)).values())

    # Nada de la cuenta anterior sirve para la nueva.
    for token in old.sessions:
        assert (await client.get(ME_URL, headers=with_session(token))).status_code == 401
    assert (await client.post(VERIFY_URL, json={"token": old.first_verification_token})).status_code == 410

    assert (await login(EMAIL, "clave-antigua-1")).status_code == 401
    new_login = await login(EMAIL, "clave-nueva-22")
    assert new_login.status_code == 200

    me = await client.get(ME_URL, headers=with_session(session_token(new_login)))
    assert me.json() == {
        "id": str(new_id),
        "nickname": "Renacido",
        "program": {"code": "ING-SIS", "name": "Ingeniería de Sistemas"},
        "onboarding_completed": False,
    }


# --- Concurrencia y logs -------------------------------------------------------------


async def test_doble_clic_elimina_una_vez_y_la_segunda_peticion_da_401(
    client: httpx.AsyncClient, create_account, user_footprint
) -> None:
    account = await create_account()

    responses = await asyncio.gather(
        _delete(client, account.sessions[0], json={"confirm": True}),
        _delete(client, account.sessions[0], json={"confirm": True}),
    )

    assert sorted(r.status_code for r in responses) == [204, 401]
    assert (await user_footprint(account.id))["users"] == 0


async def test_si_el_delete_no_afecta_filas_responde_401_y_borra_la_cookie(
    client: httpx.AsyncClient, create_account, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = await create_account()

    async def _already_deleted(self: AuthRepository, user_id: uuid.UUID) -> bool:
        return False

    monkeypatch.setattr(AuthRepository, "delete_user", _already_deleted)
    response = await _delete(client, account.sessions[0], json={"confirm": True})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert_session_cookie_deleted(response)


async def test_logs_de_eliminacion_no_contienen_correo_ni_user_id(
    client: httpx.AsyncClient, create_account, caplog: pytest.LogCaptureFixture
) -> None:
    account = await create_account()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("fitia")
    logger.addHandler(handler)
    caplog.set_level(logging.DEBUG)
    try:
        await _delete(client, account.sessions[0], json={"confirm": True})
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue() + caplog.text
    assert "account_deleted" in output
    assert account.email not in output
    assert str(account.id) not in output
