"""HU 1 - Registro: AC-1-1 a AC-1-6, AC-1-9, NFR-01, NFR-07, NFR-08 y protecciones transversales."""
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import FrozenClock
from app.core.security import hash_token
from app.main import app
from app.modules.auth.models import Consent, EmailVerificationToken, User
from app.modules.auth.repository import AuthRepository
from tests.conftest import CSRF_HEADERS, FRONTEND_URL, valid_payload
from tests.fakes import FakeMailer

REGISTER_URL = "/api/v1/auth/register"
EMAIL = "ana.gomez@correounivalle.edu.co"


async def _user_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(User)) or 0


def _field_codes(response: httpx.Response) -> dict[str, str]:
    return {f["field"]: f["code"] for f in response.json()["error"]["fields"]}


# --- Criterios de aceptación -------------------------------------------------


async def test_ac_1_1_registro_valido_crea_cuenta_pendiente_y_envia_enlace(
    register, db: AsyncSession, mailer: FakeMailer, clock: FrozenClock
) -> None:
    response = await register()

    assert response.status_code == 201
    assert response.json() == {"status": "pending_verification"}

    user = await db.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    assert user.email_verified_at is None
    assert user.nickname == "Pantera"
    assert user.program_code == "ING-SIS"
    assert user.role == "student"

    consent = await db.scalar(select(Consent).where(Consent.user_id == user.id))
    assert consent is not None
    assert consent.text_version == "2026-01"
    assert consent.accepted_at == clock.now()

    token_row = await db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
    assert token_row is not None
    assert token_row.used_at is None
    assert token_row.expires_at == clock.now() + timedelta(hours=24)

    assert len(mailer.sent) == 1
    assert mailer.sent[0].to == EMAIL
    assert mailer.last_link().startswith(f"{FRONTEND_URL}/verificar-correo?token=")
    assert hash_token(mailer.last_token()) == token_row.token_hash


async def test_ac_1_2_dominio_no_institucional_es_rechazado(register, db: AsyncSession, mailer: FakeMailer) -> None:
    response = await register(email="ana.gomez@gmail.com")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "DOMAIN_NOT_ALLOWED"
    assert error["message"] == "Solo se admiten correos @correounivalle.edu.co"
    assert _field_codes(response) == {"email": "DOMAIN_NOT_ALLOWED"}
    assert await _user_count(db) == 0
    assert mailer.sent == []


async def test_ac_1_3_correo_ya_registrado_no_se_duplica(register, db: AsyncSession) -> None:
    assert (await register()).status_code == 201

    response = await register(email="  ANA.Gomez@CorreoUnivalle.edu.co ", nickname="Otro apodo")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_EXISTS"
    assert "Ya existe una cuenta" in response.json()["error"]["message"]
    assert await _user_count(db) == 1


async def test_ac_1_3_carrera_de_registros_simultaneos_devuelve_409(
    register, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (await register()).status_code == 201

    async def _not_seen(self: AuthRepository, email: str) -> bool:  # simula que la otra petición aún no confirmaba
        return False

    monkeypatch.setattr(AuthRepository, "email_exists", _not_seen)
    response = await register()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_EXISTS"
    assert await _user_count(db) == 1


@pytest.mark.parametrize("program_code", ["__omit__", None, "", "NO-EXISTE"])
async def test_ac_1_4_sin_programa_se_impide_y_senala_el_campo(
    register, omit, db: AsyncSession, program_code: object
) -> None:
    response = await register(program_code=omit if program_code == "__omit__" else program_code)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _field_codes(response) == {"program_code": "PROGRAM_REQUIRED"}
    assert await _user_count(db) == 0


async def test_ac_1_5_correo_con_espacios_y_mayusculas_se_normaliza(
    register, db: AsyncSession, mailer: FakeMailer
) -> None:
    response = await register(email="   Ana.GOMEZ@CorreoUnivalle.EDU.CO  ")

    assert response.status_code == 201
    stored = await db.scalar(select(User.email))
    assert stored == EMAIL
    assert mailer.sent[0].to == EMAIL


@pytest.mark.parametrize("accepted", ["__omit__", None, False])
async def test_ac_1_6_sin_aceptar_tratamiento_de_datos_no_se_crea_cuenta(
    register, omit, db: AsyncSession, accepted: object
) -> None:
    response = await register(accepted_terms=omit if accepted == "__omit__" else accepted)

    assert response.status_code == 422
    assert _field_codes(response) == {"accepted_terms": "TERMS_REQUIRED"}
    assert "aceptar" in response.json()["error"]["message"]
    assert await _user_count(db) == 0
    assert await db.scalar(select(func.count()).select_from(Consent)) == 0


@pytest.mark.parametrize("nickname", ["", "   ", "ab", "  ab  ", "a" * 21, None])
async def test_ac_1_9_apodo_fuera_de_rango_se_impide(register, db: AsyncSession, nickname: str | None) -> None:
    response = await register(nickname=nickname)

    assert response.status_code == 422
    assert _field_codes(response) == {"nickname": "NICKNAME_LENGTH"}
    assert "entre 3 y 20" in response.json()["error"]["message"]
    assert await _user_count(db) == 0


@pytest.mark.parametrize("nickname", ["abc", "a" * 20, "  Ana  "])
async def test_ac_1_9_apodo_en_los_limites_es_aceptado(register, db: AsyncSession, nickname: str) -> None:
    response = await register(nickname=nickname)

    assert response.status_code == 201
    assert await db.scalar(select(User.nickname)) == nickname.strip()


async def test_apodo_no_es_unico(register, db: AsyncSession) -> None:
    assert (await register(email="a@correounivalle.edu.co")).status_code == 201
    assert (await register(email="b@correounivalle.edu.co")).status_code == 201
    assert await _user_count(db) == 2


# --- Validación acumulada y otros campos ------------------------------------


async def test_errores_de_campo_se_devuelven_todos_juntos(client: httpx.AsyncClient, db: AsyncSession) -> None:
    response = await client.post(REGISTER_URL, json={"email": "sin-arroba", "password": "corta"})

    assert response.status_code == 422
    assert _field_codes(response) == {
        "nickname": "NICKNAME_LENGTH",
        "program_code": "PROGRAM_REQUIRED",
        "accepted_terms": "TERMS_REQUIRED",
        "password": "WEAK_PASSWORD",
        "email": "INVALID_EMAIL",
    }
    assert await _user_count(db) == 0


@pytest.mark.parametrize("password", [None, "", "1234567"])
async def test_contrasena_menor_a_8_caracteres_es_rechazada(register, password: str | None) -> None:
    response = await register(password=password)

    assert response.status_code == 422
    assert _field_codes(response) == {"password": "WEAK_PASSWORD"}


async def test_cuerpo_con_tipos_invalidos_usa_formato_uniforme(client: httpx.AsyncClient) -> None:
    response = await client.post(REGISTER_URL, json=valid_payload(accepted_terms="si"))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["fields"] == [{"field": "accepted_terms", "code": "INVALID"}]


async def test_json_mal_formado_usa_formato_uniforme(client: httpx.AsyncClient) -> None:
    response = await client.post(
        REGISTER_URL, content=b"{no es json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- Seguridad ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "code"),
    [
        ("ana@correounivalle.edu.co.evil.com", "DOMAIN_NOT_ALLOWED"),
        ("ana@sub.correounivalle.edu.co", "DOMAIN_NOT_ALLOWED"),
        ("ana@evilcorreounivalle.edu.co", "DOMAIN_NOT_ALLOWED"),
        ("ana@correounivalle.edu", "DOMAIN_NOT_ALLOWED"),
        ("ana@correounivalle.edu.co@gmail.com", "VALIDATION_ERROR"),
        ("ana@gmail.com@correounivalle.edu.co", "VALIDATION_ERROR"),
        ("@correounivalle.edu.co", "VALIDATION_ERROR"),
        ("ana gomez@correounivalle.edu.co", "VALIDATION_ERROR"),
    ],
)
async def test_correos_maliciosos_o_mal_formados_son_rechazados(
    register, db: AsyncSession, email: str, code: str
) -> None:
    response = await register(email=email)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert await _user_count(db) == 0


async def test_nfr_08_contrasena_se_guarda_con_argon2id(register, db: AsyncSession) -> None:
    await register(password="contrasena-segura")

    password_hash = await db.scalar(select(User.password_hash))
    assert password_hash is not None
    assert password_hash.startswith("$argon2id$")
    assert "contrasena-segura" not in password_hash


async def test_nfr_09_token_de_verificacion_se_guarda_solo_como_hash(
    register, db: AsyncSession, mailer: FakeMailer
) -> None:
    await register()
    token = mailer.last_token()

    stored = (await db.scalars(select(EmailVerificationToken.token_hash))).all()
    assert stored == [hash_token(token)]
    assert token not in stored


async def test_nfr_07_check_de_bd_rechaza_insert_directo_con_otro_dominio(db: AsyncSession, clock: FrozenClock) -> None:
    with pytest.raises(IntegrityError, match="ck_users_email_domain"):
        await db.execute(
            insert(User).values(
                email="intruso@gmail.com",
                password_hash="x",
                nickname="Intruso",
                program_code="ING-SIS",
                created_at=clock.now(),
            )
        )


async def test_check_de_bd_rechaza_apodo_fuera_de_rango(db: AsyncSession, clock: FrozenClock) -> None:
    with pytest.raises(IntegrityError, match="ck_users_nickname_length"):
        await db.execute(
            insert(User).values(
                email="corto@correounivalle.edu.co",
                password_hash="x",
                nickname="ab",
                program_code="ING-SIS",
                created_at=clock.now(),
            )
        )


async def test_sin_encabezado_x_requested_with_devuelve_403(client: httpx.AsyncClient, db: AsyncSession) -> None:
    response = await client.post(REGISTER_URL, json=valid_payload(), headers={"X-Requested-With": ""})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_HEADER_MISSING"
    assert await _user_count(db) == 0


async def test_registro_aplica_rate_limit_por_correo(register) -> None:
    statuses = [(await register(nickname=n)).status_code for n in ["uno", "dos", "tres", "cuatro", "cinco", "seis"]]

    assert statuses[0] == 201
    assert statuses[1:5] == [409] * 4
    assert statuses[5] == 429


async def test_registro_aplica_rate_limit_por_ip(client: httpx.AsyncClient, settings) -> None:
    settings.RATE_LIMIT_PER_IP = 3
    for i in range(3):
        await client.post(REGISTER_URL, json=valid_payload(email=f"u{i}@correounivalle.edu.co"))

    response = await client.post(REGISTER_URL, json=valid_payload(email="u9@correounivalle.edu.co"))

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert int(response.headers["Retry-After"]) > 0


# --- NFR-01: el correo no bloquea la respuesta -------------------------------


class _ResponseSentProbe:
    """Middleware ASGI de prueba que marca cuándo se terminó de enviar la respuesta."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.response_sent = False

    async def __call__(self, scope, receive, send) -> None:
        async def _send(message) -> None:
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                self.response_sent = True

        await self.inner(scope, receive, _send)


async def test_nfr_01_registro_responde_sin_esperar_el_envio_del_correo(client: httpx.AsyncClient, mailer) -> None:
    probe = _ResponseSentProbe(app)
    observed: list[bool] = []
    original_send = mailer.send

    async def _spy(message) -> None:
        observed.append(probe.response_sent)
        await original_send(message)

    mailer.send = _spy
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=probe), base_url="http://test", headers=CSRF_HEADERS
    ) as probe_client:
        response = await probe_client.post(REGISTER_URL, json=valid_payload())

    assert response.status_code == 201
    assert observed == [True], "el correo debe enviarse después de entregar la respuesta"


async def test_fallo_del_proveedor_de_correo_no_afecta_el_registro(register, mailer, db: AsyncSession) -> None:
    async def _boom(message) -> None:
        raise RuntimeError("proveedor caído")

    mailer.send = _boom
    response = await register()

    assert response.status_code == 201
    assert await _user_count(db) == 1
