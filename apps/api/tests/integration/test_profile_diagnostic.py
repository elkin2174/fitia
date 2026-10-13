"""HU 6 - Consultar y actualizar diagnóstico del estudiante: AC-6-1 a AC-6-5."""
import time
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters.fake_text import FakeTextAdapter
from app.core.clock import FrozenClock
from app.core.config import Settings
from app.modules.auth.models import User
from app.modules.plan.models import PlanDay, PlanExercise, WeeklyPlan
from app.modules.profile.models import Profile, ProfileTrainingDay
from tests.conftest import VALID_DIAGNOSTIC, Student, with_session
from tests.fakes import ManualScheduler

PROFILE_URL = "/api/v1/profile"


async def _get_profile(client: httpx.AsyncClient, token: str) -> httpx.Response:
    return await client.get(PROFILE_URL, headers=with_session(token))


async def _patch_profile(client: httpx.AsyncClient, token: str, payload: Any) -> httpx.Response:
    return await client.patch(PROFILE_URL, json=payload, headers=with_session(token))


async def _put_profile(client: httpx.AsyncClient, token: str, payload: Any) -> httpx.Response:
    return await client.put(PROFILE_URL, json=payload, headers=with_session(token))


# --- AC-6-1: Consulta del diagnóstico -----------------------------------------


async def test_ac_6_1_estudiante_consulta_su_diagnostico_actual(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    response = await _get_profile(client, student_with_profile.token)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"

    data = response.json()
    assert "profile" in data
    profile = data["profile"]
    assert profile["goal"] == VALID_DIAGNOSTIC["goal"]
    assert profile["term_weeks"] == VALID_DIAGNOSTIC["term_weeks"]
    assert profile["fitness_level"] == VALID_DIAGNOSTIC["fitness_level"]
    assert profile["session_minutes"] == VALID_DIAGNOSTIC["session_minutes"]
    assert profile["has_machine_access"] == VALID_DIAGNOSTIC["has_machine_access"]
    assert profile["training_days"] == [1, 3, 5]  # ordenados


async def test_ac_6_1_estudiante_sin_diagnostico_recibe_403(client: httpx.AsyncClient, student: Student) -> None:
    response = await _get_profile(client, student.token)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ONBOARDING_REQUIRED"


async def test_ac_6_1_sin_sesion_recibe_401(client: httpx.AsyncClient) -> None:
    response = await client.get(PROFILE_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_ac_6_1_no_expone_datos_de_otro_estudiante(
    client: httpx.AsyncClient,
    student_with_profile: Student,
    make_student: Any,
    complete_diagnostic: Any,
) -> None:
    other_student = await make_student("otro.estudiante@correounivalle.edu.co")
    other_diagnostic = VALID_DIAGNOSTIC | {
        "goal": "weight_loss",
        "term_weeks": 4,
        "fitness_level": "advanced",
        "session_minutes": 60,
        "training_days": [2, 4],
        "has_machine_access": False,
    }
    await complete_diagnostic(other_student.token, other_diagnostic)

    res1 = await _get_profile(client, student_with_profile.token)
    res2 = await _get_profile(client, other_student.token)

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["profile"]["goal"] == "strength"
    assert res2.json()["profile"]["goal"] == "weight_loss"
    assert res1.json()["profile"]["training_days"] == [1, 3, 5]
    assert res2.json()["profile"]["training_days"] == [2, 4]


async def test_ac_6_1_apodo_y_programa_no_forman_parte_del_diagnostico(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    response = await _get_profile(client, student_with_profile.token)

    assert response.status_code == 200
    profile = response.json()["profile"]
    assert "nickname" not in profile
    assert "program" not in profile
    assert "program_code" not in profile
    assert "email" not in profile


# --- AC-6-2: Actualización correcta -------------------------------------------


async def test_ac_6_2_actualizacion_exitosa_persiste_y_devuelve_mensaje(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession, clock: FrozenClock
) -> None:
    new_answers = {
        "goal": "endurance",
        "term_weeks": 12,
        "fitness_level": "intermediate",
        "session_minutes": 45,
        "training_days": [2, 4],
        "has_machine_access": False,
    }

    start = time.perf_counter()
    response = await _patch_profile(client, student_with_profile.token, new_answers)
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert elapsed < 2.0  # NFR: respuesta en menos de 2 segundos

    body = response.json()
    assert "profile" in body
    for k, v in new_answers.items():
        assert body["profile"][k] == v
    assert "message" in body
    assert "Tu diagnóstico se actualizó correctamente" in body["message"]
    assert "próximo plan" in body["message"]
    assert "plan actual no ha cambiado" in body["message"]

    # Verificar directamente en la base de datos
    profile_db = await db.get(Profile, student_with_profile.user.id)
    assert profile_db is not None
    assert profile_db.goal == "endurance"
    assert profile_db.term_weeks == 12
    assert profile_db.fitness_level == "intermediate"
    assert profile_db.session_minutes == 45
    assert profile_db.has_machine_access is False
    assert profile_db.updated_at == clock.now()

    days_db = (
        await db.scalars(
            select(ProfileTrainingDay.weekday)
            .where(ProfileTrainingDay.user_id == student_with_profile.user.id)
            .order_by(ProfileTrainingDay.weekday)
        )
    ).all()
    assert list(days_db) == [2, 4]


async def test_ac_6_2_actualizacion_parcial_modifica_solo_los_campos_enviados(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession
) -> None:
    response = await _patch_profile(client, student_with_profile.token, {"goal": "weight_loss"})

    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["goal"] == "weight_loss"
    assert profile["term_weeks"] == VALID_DIAGNOSTIC["term_weeks"]
    assert profile["training_days"] == [1, 3, 5]

    profile_db = await db.get(Profile, student_with_profile.user.id)
    assert profile_db is not None
    assert profile_db.goal == "weight_loss"


async def test_ac_6_2_consulta_posterior_devuelve_valores_guardados(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    await _patch_profile(client, student_with_profile.token, {"goal": "general_health", "training_days": [1, 2, 3]})

    follow_up = await _get_profile(client, student_with_profile.token)

    assert follow_up.status_code == 200
    assert follow_up.json()["profile"]["goal"] == "general_health"
    assert follow_up.json()["profile"]["training_days"] == [1, 2, 3]


async def test_ac_6_2_no_modifica_apodo_ni_programa_ni_otros_usuarios(
    client: httpx.AsyncClient,
    student_with_profile: Student,
    make_student: Any,
    complete_diagnostic: Any,
    db: AsyncSession,
) -> None:
    other_student = await make_student("otro2@correounivalle.edu.co")
    await complete_diagnostic(other_student.token, VALID_DIAGNOSTIC)

    malicious_payload = {
        "goal": "endurance",
        "nickname": "NuevoApodo",
        "program_code": "ING-CIVIL",
        "user_id": str(other_student.user.id),
    }
    response = await _patch_profile(client, student_with_profile.token, malicious_payload)

    assert response.status_code == 200

    # Usuario propio no modificó nickname ni programa
    user_db = await db.get(User, student_with_profile.user.id)
    assert user_db is not None
    assert user_db.nickname == "Pantera"
    assert user_db.program_code == "ING-SIS"

    # Otro usuario permanece intacto
    other_profile = await db.get(Profile, other_student.user.id)
    assert other_profile is not None
    assert other_profile.goal == "strength"


async def test_ac_6_2_actualizacion_con_mismos_valores_evita_escritura_innecesaria(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession
) -> None:
    profile_before = await db.get(Profile, student_with_profile.user.id)
    assert profile_before is not None
    initial_updated_at = profile_before.updated_at

    response = await _patch_profile(client, student_with_profile.token, VALID_DIAGNOSTIC)

    assert response.status_code == 200
    profile_after = await db.get(Profile, student_with_profile.user.id)
    assert profile_after is not None
    assert profile_after.updated_at == initial_updated_at


async def test_ac_6_2_put_profile_soporta_actualizacion(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    response = await _put_profile(
        client,
        student_with_profile.token,
        VALID_DIAGNOSTIC | {"goal": "endurance", "term_weeks": 4},
    )

    assert response.status_code == 200
    assert response.json()["profile"]["goal"] == "endurance"
    assert response.json()["profile"]["term_weeks"] == 4


# --- AC-6-3: Datos inválidos --------------------------------------------------


async def test_ac_6_3_datos_invalidos_rechazan_operacion_y_preservan_estado_anterior(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession
) -> None:
    response = await _patch_profile(client, student_with_profile.token, {"goal": "invalid_goal"})

    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(e["field"] == "goal" and e["code"] == "INVALID_OPTION" for e in data["error"]["fields"])

    # El perfil anterior permanece intacto
    profile_db = await db.get(Profile, student_with_profile.user.id)
    assert profile_db is not None
    assert profile_db.goal == "strength"


async def test_ac_6_3_training_days_vacio_falla_con_days_required(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession
) -> None:
    response = await _patch_profile(client, student_with_profile.token, {"training_days": []})

    assert response.status_code == 422
    data = response.json()
    assert any(e["field"] == "training_days" and e["code"] == "DAYS_REQUIRED" for e in data["error"]["fields"])

    days_db = (
        await db.scalars(
            select(ProfileTrainingDay.weekday).where(ProfileTrainingDay.user_id == student_with_profile.user.id)
        )
    ).all()
    assert len(days_db) == 3


async def test_ac_6_3_training_days_fuera_de_rango_falla(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    response = await _patch_profile(client, student_with_profile.token, {"training_days": [0, 6]})

    assert response.status_code == 422
    assert any(e["field"] == "training_days" and e["code"] == "INVALID_OPTION" for e in response.json()["error"]["fields"])


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("term_weeks", True),  # bool no pasa como int
        ("term_weeks", "8"),
        ("session_minutes", False),
        ("session_minutes", "30"),
        ("fitness_level", "superman"),
        ("has_machine_access", 1),
    ],
)
async def test_ac_6_3_tipado_incorrecto_falla(
    client: httpx.AsyncClient, student_with_profile: Student, field: str, bad_value: Any
) -> None:
    response = await _patch_profile(client, student_with_profile.token, {field: bad_value})

    assert response.status_code == 422
    assert any(e["field"] == field and e["code"] == "INVALID_OPTION" for e in response.json()["error"]["fields"])


async def test_ac_6_3_cuerpo_vacio_falla_con_empty_update(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    response = await _patch_profile(client, student_with_profile.token, {})

    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(e["code"] == "EMPTY_UPDATE" for e in data["error"]["fields"])


async def test_ac_6_3_cuerpo_solo_con_campos_desconocidos_falla(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession
) -> None:
    response = await _patch_profile(client, student_with_profile.token, {"campo_inventado": 123})

    assert response.status_code == 422
    assert any(e["code"] == "EMPTY_UPDATE" for e in response.json()["error"]["fields"])

    profile_db = await db.get(Profile, student_with_profile.user.id)
    assert profile_db is not None
    assert profile_db.goal == "strength"



# --- AC-6-4: El plan vigente no cambia ----------------------------------------


async def test_ac_6_4_plan_vigente_permanece_completamente_intacto_tras_actualizar_perfil(
    client: httpx.AsyncClient,
    student_with_profile: Student,
    plan_api: Any,
    manual_scheduler: ManualScheduler,
    db: AsyncSession,
) -> None:
    token = student_with_profile.token

    # 1. Generar plan vigente
    started = await plan_api.generate(token)
    assert started.status_code == 202
    await manual_scheduler.run_all()

    current_before = await plan_api.current(token)
    assert current_before.status_code == 200
    plan_data_before = current_before.json()
    assert plan_data_before["status"] == "ready"
    assert plan_data_before["outdated"] is False

    # Instantánea completa de la BD antes de editar el perfil
    plan_row_before = await db.scalar(
        select(WeeklyPlan).where(WeeklyPlan.user_id == student_with_profile.user.id, WeeklyPlan.status == "ready")
    )
    assert plan_row_before is not None
    plan_id = plan_row_before.id
    gen_number = plan_row_before.generation_number
    snapshot_before = plan_row_before.profile_snapshot
    week_start = plan_row_before.week_start
    start_date = plan_row_before.start_date

    days_count_before = await db.scalar(select(text("count(*) FROM plan_days WHERE plan_id = :id")), {"id": plan_id})
    exercises_count_before = await db.scalar(
        select(text("count(*) FROM plan_exercises WHERE plan_id = :id")), {"id": plan_id}
    )

    # 2. Modificar el diagnóstico del estudiante
    update_res = await _patch_profile(
        client,
        token,
        {
            "goal": "endurance",
            "session_minutes": 15,
            "training_days": [2, 4],
        },
    )
    assert update_res.status_code == 200

    # 3. Comprobar que el plan en BD no cambió en lo absoluto
    plan_row_after = await db.get(WeeklyPlan, plan_id)
    assert plan_row_after is not None
    assert plan_row_after.status == "ready"
    assert plan_row_after.generation_number == gen_number
    assert plan_row_after.profile_snapshot == snapshot_before  # conserva snapshot histórico
    assert plan_row_after.week_start == week_start
    assert plan_row_after.start_date == start_date

    days_count_after = await db.scalar(select(text("count(*) FROM plan_days WHERE plan_id = :id")), {"id": plan_id})
    exercises_count_after = await db.scalar(
        select(text("count(*) FROM plan_exercises WHERE plan_id = :id")), {"id": plan_id}
    )
    assert days_count_after == days_count_before
    assert exercises_count_after == exercises_count_before

    # 4. Comprobar que el plan reporta outdated: True en la API
    current_after = await plan_api.current(token)
    assert current_after.status_code == 200
    plan_data_after = current_after.json()
    assert plan_data_after["status"] == "ready"
    assert plan_data_after["outdated"] is True
    assert plan_data_after["can_regenerate"] is True
    assert plan_data_after["days"] == plan_data_before["days"]  # mismos días visibles


# --- AC-6-5: Nuevo plan con el diagnóstico actualizado ------------------------


async def test_ac_6_5_proximo_plan_utiliza_respuestas_actualizadas(
    client: httpx.AsyncClient,
    student_with_profile: Student,
    plan_api: Any,
    manual_scheduler: ManualScheduler,
    db: AsyncSession,
    fake_ai: FakeTextAdapter,
) -> None:
    token = student_with_profile.token

    # 1. Generar plan inicial
    await plan_api.generate(token)
    await manual_scheduler.run_all()
    assert fake_ai.calls == 1

    # 2. Actualizar diagnóstico
    updated_answers = {
        "goal": "endurance",
        "term_weeks": 12,
        "fitness_level": "intermediate",
        "session_minutes": 15,
        "training_days": [2, 4],
        "has_machine_access": False,
    }
    await _patch_profile(client, token, updated_answers)

    # 3. Solicitar nuevo plan
    new_gen = await plan_api.generate(token)
    assert new_gen.status_code == 202
    await manual_scheduler.run_all()

    # 4. Verificar que la IA recibió las respuestas actualizadas
    assert fake_ai.calls == 2
    last_ai_request = fake_ai.requests[-1]
    assert last_ai_request.input_data["goal"] == "endurance"
    assert last_ai_request.input_data["session_minutes"] == 15
    assert last_ai_request.input_data["training_days"] == [2, 4]
    assert last_ai_request.input_data["has_machine_access"] is False

    # 5. Verificar que el nuevo plan vigente en la API refleja el nuevo snapshot
    current = await plan_api.current(token)
    assert current.status_code == 200
    assert current.json()["status"] == "ready"
    assert current.json()["outdated"] is False
    assert current.json()["generation_number"] == 2


async def test_ac_6_5_limite_semanal_de_regeneracion_se_respeta_estrictamente(
    client: httpx.AsyncClient,
    student_with_profile: Student,
    plan_api: Any,
    manual_scheduler: ManualScheduler,
    settings: Settings,
) -> None:
    token = student_with_profile.token

    # Generación 1
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    # Generación 2
    await _patch_profile(client, token, {"goal": "endurance"})
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    # Generación 3 (alcanza el límite de PLAN_MAX_GENERATIONS_PER_WEEK=3)
    await _patch_profile(client, token, {"goal": "weight_loss"})
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    # Actualizar perfil por cuarta vez: la actualización de perfil sí es exitosa
    patch_res = await _patch_profile(client, token, {"goal": "general_health"})
    assert patch_res.status_code == 200

    # Pero generar una cuarta rutina dentro de la misma semana está prohibido (429)
    fourth_gen = await plan_api.generate(token)
    assert fourth_gen.status_code == 429
    assert fourth_gen.json()["error"]["code"] == "REGENERATION_LIMIT"
    assert "Retry-After" in fourth_gen.headers

