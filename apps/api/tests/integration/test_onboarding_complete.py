"""HU 4 - POST /onboarding/complete: AC-4-1 a AC-4-5, NFR-04, NFR-10, NFR-12 y NFR-13."""
import asyncio
import io
import logging
import time
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import FrozenClock
from app.core.logging import JsonFormatter
from app.main import app
from app.modules.profile.models import Profile, ProfileTrainingDay
from app.modules.profile.repository import ProfileRepository
from tests.conftest import COMPLETE_URL, PASSWORD, VALID_DIAGNOSTIC, Student, session_token, with_session
from tests.fakes import FakeMailer

ME_URL = "/api/v1/me"
ALL_FIELDS_MISSING = [
    {"field": "goal", "code": "REQUIRED"},
    {"field": "term_weeks", "code": "REQUIRED"},
    {"field": "fitness_level", "code": "REQUIRED"},
    {"field": "session_minutes", "code": "REQUIRED"},
    {"field": "has_machine_access", "code": "MACHINE_ACCESS_REQUIRED"},
    {"field": "training_days", "code": "DAYS_REQUIRED"},
]
REQUIRED_CODE = {f["field"]: f["code"] for f in ALL_FIELDS_MISSING}


async def _rows(db: AsyncSession) -> tuple[int, int]:
    profiles = await db.scalar(select(func.count()).select_from(Profile)) or 0
    days = await db.scalar(select(func.count()).select_from(ProfileTrainingDay)) or 0
    return profiles, days


async def _stored_days(db: AsyncSession, student: Student) -> list[int]:
    result = await db.scalars(
        select(ProfileTrainingDay.weekday)
        .where(ProfileTrainingDay.user_id == student.user.id)
        .order_by(ProfileTrainingDay.weekday)
    )
    return list(result.all())


def _without(field: str) -> dict[str, Any]:
    return {k: v for k, v in VALID_DIAGNOSTIC.items() if k != field}


# --- AC-4-1: guardar el diagnóstico ----------------------------------------------------


async def test_ac_4_1_diagnostico_completo_se_guarda_y_permite_generar_el_plan(
    client: httpx.AsyncClient, student: Student, complete_diagnostic, db: AsyncSession, clock: FrozenClock
) -> None:
    response = await complete_diagnostic(student.token)

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "profile": {
            "goal": "strength",
            "term_weeks": 8,
            "fitness_level": "beginner",
            "session_minutes": 30,
            "training_days": [1, 3, 5],
            "has_machine_access": True,
        }
    }

    profile = await db.scalar(select(Profile).where(Profile.user_id == student.user.id))
    assert profile is not None
    assert (profile.goal, profile.term_weeks, profile.fitness_level, profile.session_minutes) == (
        "strength",
        8,
        "beginner",
        30,
    )
    assert profile.has_machine_access is True
    assert profile.created_at == profile.updated_at == clock.now()
    assert await _stored_days(db, student) == [1, 3, 5]

    me = await client.get(ME_URL, headers=with_session(student.token))
    assert me.json()["onboarding_completed"] is True


async def test_respuesta_no_incluye_user_id_ni_fechas(student: Student, complete_diagnostic) -> None:
    response = await complete_diagnostic(student.token)

    assert str(student.user.id) not in response.text
    assert "created_at" not in response.text and "updated_at" not in response.text
    assert student.user.email not in response.text


async def test_dias_repetidos_se_guardan_una_vez_y_ordenados(
    student: Student, complete_diagnostic, db: AsyncSession
) -> None:
    response = await complete_diagnostic(student.token, VALID_DIAGNOSTIC | {"training_days": [3, 1, 3, 1]})

    assert response.json()["profile"]["training_days"] == [1, 3]
    assert await _stored_days(db, student) == [1, 3]


# --- AC-4-2 / AC-4-3: preguntas sin responder --------------------------------------------


@pytest.mark.parametrize("field", list(REQUIRED_CODE))
@pytest.mark.parametrize("mode", ["omitido", "null"])
async def test_ac_4_2_pregunta_sin_responder_se_senala(
    student: Student, complete_diagnostic, db: AsyncSession, field: str, mode: str
) -> None:
    body = _without(field) if mode == "omitido" else VALID_DIAGNOSTIC | {field: None}

    response = await complete_diagnostic(student.token, body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["fields"] == [{"field": field, "code": REQUIRED_CODE[field]}]
    assert await _rows(db) == (0, 0)


@pytest.mark.parametrize(
    "raw", [b"{}", b"null", b"[]", b'"texto"', b""], ids=["objeto-vacio", "null", "lista", "texto", "sin-cuerpo"]
)
async def test_ac_4_2_cuerpo_vacio_o_no_objeto_senala_todas_las_preguntas(
    student: Student, complete_diagnostic, db: AsyncSession, raw: bytes
) -> None:
    response = await complete_diagnostic(student.token, raw=raw)

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == ALL_FIELDS_MISSING
    assert await _rows(db) == (0, 0)


async def test_json_mal_formado_sigue_el_422_estandar(student: Student, complete_diagnostic) -> None:
    response = await complete_diagnostic(student.token, raw=b"{no es json")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["fields"][0]["code"] == "INVALID_JSON"


@pytest.mark.parametrize("days", ["__omit__", None, []], ids=["ausente", "null", "lista-vacia"])
async def test_ac_4_3_sin_dias_pide_elegir_al_menos_uno(
    student: Student, complete_diagnostic, db: AsyncSession, days: object
) -> None:
    body = _without("training_days") if days == "__omit__" else VALID_DIAGNOSTIC | {"training_days": days}

    response = await complete_diagnostic(student.token, body)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["fields"] == [{"field": "training_days", "code": "DAYS_REQUIRED"}]
    assert "al menos un día" in error["message"]
    assert "lunes a viernes" in error["message"]
    assert await _rows(db) == (0, 0)


# --- AC-4-4: valores fuera de las opciones (NFR-13) --------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("goal", "yoga"),
        ("goal", "STRENGTH"),
        ("term_weeks", 5),
        ("term_weeks", "4"),
        ("term_weeks", 4.0),
        ("term_weeks", True),
        ("fitness_level", "pro"),
        ("session_minutes", 20),
        ("has_machine_access", "si"),
        ("has_machine_access", 1),
        ("has_machine_access", "true"),
        ("training_days", [0]),
        ("training_days", [6]),
        ("training_days", [1, "2"]),
        ("training_days", "1"),
        ("training_days", [True]),
        ("training_days", {"lunes": True}),
    ],
)
async def test_ac_4_4_valor_fuera_de_las_opciones_es_rechazado(
    student: Student, complete_diagnostic, db: AsyncSession, field: str, value: object
) -> None:
    response = await complete_diagnostic(student.token, VALID_DIAGNOSTIC | {field: value})

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == [{"field": field, "code": "INVALID_OPTION"}]
    assert await _rows(db) == (0, 0)


async def test_ac_4_4_un_dia_invalido_no_deja_perfil_ni_dias(
    student: Student, complete_diagnostic, db: AsyncSession
) -> None:
    response = await complete_diagnostic(student.token, VALID_DIAGNOSTIC | {"training_days": [1, 2, 9]})

    assert response.status_code == 422
    assert await _rows(db) == (0, 0)


async def test_ac_4_4_varios_errores_se_devuelven_juntos(student: Student, complete_diagnostic) -> None:
    body = {"goal": "yoga", "term_weeks": 8, "session_minutes": "30", "training_days": []}

    response = await complete_diagnostic(student.token, body)

    assert response.json()["error"]["fields"] == [
        {"field": "goal", "code": "INVALID_OPTION"},
        {"field": "fitness_level", "code": "REQUIRED"},
        {"field": "session_minutes", "code": "INVALID_OPTION"},
        {"field": "has_machine_access", "code": "MACHINE_ACCESS_REQUIRED"},
        {"field": "training_days", "code": "DAYS_REQUIRED"},
    ]


# --- AC-4-5: una sola vez; después va a la pantalla principal ----------------------------


async def test_ac_4_5_con_diagnostico_completo_el_login_va_a_home(
    client: httpx.AsyncClient, student: Student, complete_diagnostic, login
) -> None:
    await complete_diagnostic(student.token)

    response = await login(student.user.email)

    assert response.json()["next"] == "home"
    me = await client.get(ME_URL, headers=with_session(session_token(response)))
    assert me.json()["onboarding_completed"] is True


async def test_ac_4_5_sin_diagnostico_el_login_va_a_onboarding(
    client: httpx.AsyncClient, student: Student, login
) -> None:
    response = await login(student.user.email)

    assert response.json()["next"] == "onboarding"
    me = await client.get(ME_URL, headers=with_session(session_token(response)))
    assert me.json()["onboarding_completed"] is False


async def test_ac_4_5_segundo_envio_devuelve_409_y_no_modifica_el_perfil(
    student: Student, complete_diagnostic, db: AsyncSession, clock: FrozenClock
) -> None:
    assert (await complete_diagnostic(student.token)).status_code == 201
    created_at = clock.now()
    clock.advance(timedelta(minutes=5))

    second = await complete_diagnostic(
        student.token,
        {
            "goal": "endurance",
            "term_weeks": 12,
            "fitness_level": "advanced",
            "session_minutes": 60,
            "training_days": [2, 4],
            "has_machine_access": False,
        },
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "PROFILE_EXISTS"
    profile = await db.scalar(select(Profile).where(Profile.user_id == student.user.id))
    assert profile is not None
    assert (profile.goal, profile.term_weeks, profile.has_machine_access) == ("strength", 8, True)
    assert profile.updated_at == created_at
    assert await _stored_days(db, student) == [1, 3, 5]


async def test_ac_4_5_un_envio_invalido_con_perfil_existente_da_422_antes_que_409(
    student: Student, complete_diagnostic
) -> None:
    await complete_diagnostic(student.token)

    response = await complete_diagnostic(student.token, {})

    assert response.status_code == 422


async def test_ac_4_5_guard_de_perfil_con_la_implementacion_real(
    client: httpx.AsyncClient, student: Student, complete_diagnostic, protected_route: str
) -> None:
    # Sin override de OnboardingStatus: ProfileOnboardingStatus consulta la tabla profiles.
    before = await client.get(protected_route, headers=with_session(student.token))
    await complete_diagnostic(student.token)
    after = await client.get(protected_route, headers=with_session(student.token))

    assert before.status_code == 403
    assert before.json()["error"]["code"] == "ONBOARDING_REQUIRED"
    assert after.status_code == 200


# --- Concurrencia y atomicidad ----------------------------------------------------------


async def test_dos_envios_simultaneos_dan_un_201_y_un_409(
    student: Student, complete_diagnostic, db: AsyncSession
) -> None:
    other_answers = VALID_DIAGNOSTIC | {"goal": "endurance", "training_days": [2, 4]}

    responses = await asyncio.gather(
        complete_diagnostic(student.token), complete_diagnostic(student.token, other_answers)
    )

    assert sorted(r.status_code for r in responses) == [201, 409]
    winner = next(r for r in responses if r.status_code == 201).json()["profile"]
    assert await _rows(db) == (1, len(winner["training_days"]))
    assert await _stored_days(db, student) == winner["training_days"]


async def test_fallo_al_guardar_los_dias_revierte_todo(
    client: httpx.AsyncClient, student: Student, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = ProfileRepository.add_training_days

    async def _broken(self: ProfileRepository, user_id, weekdays) -> None:
        await original(self, user_id, [9])  # viola ck_profile_training_days_weekday en la BD

    monkeypatch.setattr(ProfileRepository, "add_training_days", _broken)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as raw_client:
        response = await raw_client.post(
            COMPLETE_URL,
            json=VALID_DIAGNOSTIC,
            headers={**with_session(student.token), "X-Requested-With": "fitia"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "Ocurrió un error inesperado.", "fields": []}
    }
    assert await _rows(db) == (0, 0)


# --- Seguridad ----------------------------------------------------------------------------


async def test_sin_sesion_devuelve_401(client: httpx.AsyncClient, db: AsyncSession) -> None:
    response = await client.post(COMPLETE_URL, json=VALID_DIAGNOSTIC)

    assert response.status_code == 401
    assert await _rows(db) == (0, 0)


async def test_sesion_vencida_devuelve_401(student: Student, complete_diagnostic, clock: FrozenClock) -> None:
    clock.advance(timedelta(days=30, seconds=1))

    assert (await complete_diagnostic(student.token)).status_code == 401


async def test_sin_encabezado_csrf_devuelve_403_y_no_crea_nada(
    client: httpx.AsyncClient, student: Student, db: AsyncSession
) -> None:
    response = await client.post(
        COMPLETE_URL, json=VALID_DIAGNOSTIC, headers={**with_session(student.token), "X-Requested-With": ""}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_HEADER_MISSING"
    assert await _rows(db) == (0, 0)


async def test_nfr_10_user_id_y_campos_extra_del_cuerpo_se_ignoran(
    client: httpx.AsyncClient, student: Student, make_student, complete_diagnostic, db: AsyncSession, user_footprint
) -> None:
    other = await make_student("otro.estudiante@correounivalle.edu.co")
    other_before = await user_footprint(other.user.id)
    body = VALID_DIAGNOSTIC | {"user_id": str(other.user.id), "weight_kg": 70, "height_cm": 170, "nickname": "Hack"}

    response = await complete_diagnostic(student.token, body)

    assert response.status_code == 201
    assert set(response.json()["profile"]) == set(VALID_DIAGNOSTIC)
    assert await db.scalar(select(Profile.user_id)) == student.user.id
    assert await user_footprint(other.user.id) == other_before
    me = await client.get(ME_URL, headers=with_session(student.token))
    assert me.json()["nickname"] == "Pantera"


# --- NFR-12: regresión con la eliminación de cuenta (HU 3) -----------------------------


async def test_nfr_12_eliminar_cuenta_borra_perfil_y_dias_y_el_correo_empieza_de_cero(
    client: httpx.AsyncClient,
    student: Student,
    complete_diagnostic,
    user_footprint,
    register,
    login,
    mailer: FakeMailer,
) -> None:
    await complete_diagnostic(student.token)
    assert (await user_footprint(student.user.id))["profiles"] == 1

    deleted = await client.post(
        "/api/v1/me/delete-account", json={"confirm": True}, headers=with_session(student.token)
    )

    assert deleted.status_code == 204
    footprint = await user_footprint(student.user.id)
    assert footprint["profiles"] == footprint["profile_training_days"] == 0
    assert all(count == 0 for count in footprint.values())

    assert (await register(email=student.user.email, password=PASSWORD)).status_code == 201
    assert (await client.post("/api/v1/auth/verify-email", json={"token": mailer.last_token()})).status_code == 200
    relogin = await login(student.user.email)
    assert relogin.json()["next"] == "onboarding"
    token = session_token(relogin)
    me = await client.get(ME_URL, headers=with_session(token))
    assert me.json()["onboarding_completed"] is False
    assert (await complete_diagnostic(token)).status_code == 201


# --- NFR-04 y logs ----------------------------------------------------------------------


async def test_nfr_04_guardar_el_diagnostico_responde_en_menos_de_2_segundos(
    student: Student, complete_diagnostic, record_property
) -> None:
    started = time.perf_counter()
    response = await complete_diagnostic(student.token)
    elapsed = time.perf_counter() - started

    record_property("onboarding_complete_seconds", round(elapsed, 3))
    print(f"\n[NFR-04] POST /onboarding/complete: {elapsed * 1000:.0f} ms")
    assert response.status_code == 201
    assert elapsed < 2.0


async def test_logs_no_contienen_correo_ni_respuestas(
    student: Student, complete_diagnostic, caplog: pytest.LogCaptureFixture
) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("fitia")
    logger.addHandler(handler)
    caplog.set_level(logging.DEBUG)
    try:
        await complete_diagnostic(student.token)
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue() + caplog.text
    assert "diagnostic_completed" in output
    assert student.user.email not in output
    for secret in ("strength", "beginner", "goal", "training_days", "fitness_level", "has_machine_access"):
        assert secret not in output
