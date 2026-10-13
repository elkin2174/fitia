"""HU 7 - Consultar y actualizar datos del perfil del estudiante: AC-7-1 a AC-7-8 y pruebas complementarias."""
import time
import uuid
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters.fake_text import FakeTextAdapter
from app.core.clock import FrozenClock
from app.modules.auth.models import User
from app.modules.plan.models import PlanExercise, WeeklyPlan
from app.modules.profile.models import PhysicalMeasurement, Profile, ProfileTrainingDay
from tests.conftest import VALID_DIAGNOSTIC, Student, with_session
from tests.fakes import ManualScheduler

PROFILE_URL = "/api/v1/profile"
MEASUREMENTS_URL = "/api/v1/profile/measurements"
RANKING_URL = "/api/v1/ranking"


async def _get_profile(client: httpx.AsyncClient, token: str) -> httpx.Response:
    return await client.get(PROFILE_URL, headers=with_session(token))


async def _patch_profile(client: httpx.AsyncClient, token: str, payload: Any) -> httpx.Response:
    return await client.patch(PROFILE_URL, json=payload, headers=with_session(token))


async def _put_profile(client: httpx.AsyncClient, token: str, payload: Any) -> httpx.Response:
    return await client.put(PROFILE_URL, json=payload, headers=with_session(token))


# --- AC-7-1: Actualización de un campo -----------------------------------------


async def test_ac_7_1_actualizacion_campo_valido_y_consulta_posterior(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    token = student_with_profile.token

    start = time.perf_counter()
    patch_res = await _patch_profile(client, token, {"goal": "weight_loss"})
    elapsed = time.perf_counter() - start

    assert patch_res.status_code == 200
    assert elapsed < 2.0
    body = patch_res.json()
    assert body["profile"]["goal"] == "weight_loss"
    assert "message" in body

    # Consulta posterior devuelve el nuevo valor y conserva los otros
    get_res = await _get_profile(client, token)
    assert get_res.status_code == 200
    profile = get_res.json()["profile"]
    assert profile["goal"] == "weight_loss"
    assert profile["term_weeks"] == VALID_DIAGNOSTIC["term_weeks"]
    assert profile["fitness_level"] == VALID_DIAGNOSTIC["fitness_level"]
    assert profile["has_machine_access"] == VALID_DIAGNOSTIC["has_machine_access"]
    assert profile["training_days"] == [1, 3, 5]


# --- AC-7-2: Validación de errores --------------------------------------------


async def test_ac_7_2_valor_invalido_es_rechazado_y_mantiene_datos_anteriores(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession
) -> None:
    token = student_with_profile.token

    response = await _patch_profile(client, token, {"goal": "maraton_invalido", "weight_kg": -20})

    assert response.status_code == 422
    err_body = response.json()["error"]
    assert err_body["code"] == "VALIDATION_ERROR"
    fields_with_errors = {f["field"] for f in err_body["fields"]}
    assert "goal" in fields_with_errors
    assert "weight_kg" in fields_with_errors

    # Datos en base de datos permanecen intactos
    p = await db.get(Profile, student_with_profile.user.id)
    assert p is not None
    assert p.goal == VALID_DIAGNOSTIC["goal"]
    assert p.weight_kg is None


async def test_ac_7_2_campo_obligatorio_vacio_falla_con_identificacion(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    token = student_with_profile.token
    response = await _patch_profile(client, token, {"training_days": []})

    assert response.status_code == 422
    err_body = response.json()["error"]
    assert any(f["field"] == "training_days" and f["code"] == "DAYS_REQUIRED" for f in err_body["fields"])


# --- AC-7-3: Salir sin guardar ------------------------------------------------


async def test_ac_7_3_salir_sin_guardar_conserva_valores_anteriores(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession
) -> None:
    token = student_with_profile.token

    # El usuario solo consulta, no envía mutación
    res = await _get_profile(client, token)
    assert res.status_code == 200
    initial_data = res.json()["profile"]

    # En BD sigue idéntico
    p = await db.get(Profile, student_with_profile.user.id)
    assert p is not None
    assert p.goal == initial_data["goal"]
    assert p.term_weeks == initial_data["term_weeks"]


# --- AC-7-4: Acceso a máquinas ------------------------------------------------


async def test_ac_7_4_modificar_acceso_maquinas_persiste_y_aplica_al_proximo_plan(
    client: httpx.AsyncClient,
    student_with_profile: Student,
    plan_api: Any,
    manual_scheduler: ManualScheduler,
    fake_ai: FakeTextAdapter,
    db: AsyncSession,
) -> None:
    token = student_with_profile.token

    # Modificar acceso a máquinas a False
    patch_res = await _patch_profile(client, token, {"has_machine_access": False})
    assert patch_res.status_code == 200
    assert patch_res.json()["profile"]["has_machine_access"] is False

    # Verificar en BD
    p = await db.get(Profile, student_with_profile.user.id)
    assert p is not None
    assert p.has_machine_access is False

    # Al generar el siguiente plan, utiliza has_machine_access=False
    gen_res = await plan_api.generate(token)
    assert gen_res.status_code == 202
    await manual_scheduler.run_all()

    # Verificar que el AI adapter recibió has_machine_access=False
    assert fake_ai.requests[-1].input_data["has_machine_access"] is False

    # Verificar que en base de datos los ejercicios generados no requieren máquina
    plan_row = await db.scalar(
        select(WeeklyPlan).where(WeeklyPlan.user_id == student_with_profile.user.id, WeeklyPlan.status == "ready")
    )
    assert plan_row is not None
    assert plan_row.profile_snapshot["has_machine_access"] is False
    exercises = (await db.scalars(select(PlanExercise).where(PlanExercise.plan_id == plan_row.id))).all()
    assert len(exercises) > 0
    assert all(ex.requires_machine is False for ex in exercises)


# --- AC-7-5: Actualización de peso y estatura ---------------------------------


async def test_ac_7_5_actualizacion_peso_guarda_fecha_y_conserva_historial(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession, clock: FrozenClock
) -> None:
    token = student_with_profile.token
    user_id = student_with_profile.user.id

    # 1. Primera actualización de peso
    res1 = await _patch_profile(client, token, {"weight_kg": 68.5})
    assert res1.status_code == 200
    p1 = res1.json()["profile"]
    assert p1["weight_kg"] == 68.5
    assert p1["physical_updated_at"] is not None

    # Verificar en BD profiles
    profile_db = await db.get(Profile, user_id)
    assert profile_db is not None
    assert profile_db.weight_kg == 68.5
    assert profile_db.physical_updated_at == clock.now()

    # Verificar registro en historial
    m1 = (await db.scalars(select(PhysicalMeasurement).where(PhysicalMeasurement.user_id == user_id))).all()
    assert len(m1) == 1
    assert m1[0].weight_kg == 68.5

    # 2. Segunda actualización de peso más adelante en el tiempo
    clock.advance(timedelta(hours=1))  # avanza 1 hora
    res2 = await _patch_profile(client, token, {"weight_kg": 69.0})
    assert res2.status_code == 200
    p2 = res2.json()["profile"]
    assert p2["weight_kg"] == 69.0

    # Historial conserva ambos registros anteriores (no los borra)
    m2 = (
        await db.scalars(
            select(PhysicalMeasurement)
            .where(PhysicalMeasurement.user_id == user_id)
            .order_by(PhysicalMeasurement.recorded_at.desc())
        )
    ).all()
    assert len(m2) == 2
    assert m2[0].weight_kg == 69.0
    assert m2[1].weight_kg == 68.5

    # Endpoint de mediciones devuelve el historial completo
    history_res = await client.get(MEASUREMENTS_URL, headers=with_session(token))
    assert history_res.status_code == 200
    history = history_res.json()["history"]
    assert len(history) == 2
    assert history[0]["weight_kg"] == 69.0
    assert history[1]["weight_kg"] == 68.5


async def test_ac_7_5_actualizacion_peso_y_estatura_simultaneas(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession, clock: FrozenClock
) -> None:
    token = student_with_profile.token
    user_id = student_with_profile.user.id

    res = await _patch_profile(client, token, {"weight_kg": 72.0, "height_cm": 174.5})
    assert res.status_code == 200
    p = res.json()["profile"]
    assert p["weight_kg"] == 72.0
    assert p["height_cm"] == 174.5
    assert p["physical_updated_at"] is not None

    m = (await db.scalars(select(PhysicalMeasurement).where(PhysicalMeasurement.user_id == user_id))).all()
    assert len(m) == 1
    assert m[0].weight_kg == 72.0
    assert m[0].height_cm == 174.5
    assert m[0].recorded_at == clock.now()


# --- AC-7-6: Ocultar del ranking ----------------------------------------------


async def test_ac_7_6_desactivar_visibilidad_oculta_de_ranking_publico_y_conserva_puntos(
    client: httpx.AsyncClient,
    student_with_profile: Student,
    make_student: Any,
    complete_diagnostic: Any,
    db: AsyncSession,
) -> None:
    user = await db.get(User, student_with_profile.user.id)
    assert user is not None

    # Asignar puntos al estudiante
    p = await db.get(Profile, student_with_profile.user.id)
    assert p is not None
    p.points = 250
    p.level = 3
    await db.commit()

    # Usuario visible aparece en ranking público
    rank_res1 = await client.get(RANKING_URL)
    assert rank_res1.status_code == 200
    nicknames1 = [it["nickname"] for it in rank_res1.json()["items"]]
    assert user.nickname in nicknames1

    # Desactivar visibilidad
    patch_res = await _patch_profile(client, student_with_profile.token, {"is_public_ranking": False})
    assert patch_res.status_code == 200
    assert patch_res.json()["profile"]["is_public_ranking"] is False

    # Ya NO aparece en el ranking público (HU32, RANK-1)
    rank_res2 = await client.get(RANKING_URL)
    assert rank_res2.status_code == 200
    nicknames2 = [it["nickname"] for it in rank_res2.json()["items"]]
    assert user.nickname not in nicknames2

    # Conserva puntos y nivel
    get_res = await _get_profile(client, student_with_profile.token)
    assert get_res.status_code == 200
    profile = get_res.json()["profile"]
    assert profile["points"] == 250
    assert profile["level"] == 3
    assert profile["is_public_ranking"] is False


# --- AC-7-7: Reactivar visibilidad --------------------------------------------


async def test_ac_7_7_reactivar_visibilidad_reaparece_en_ranking(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession
) -> None:
    token = student_with_profile.token
    user = await db.get(User, student_with_profile.user.id)
    assert user is not None

    p = await db.get(Profile, student_with_profile.user.id)
    assert p is not None
    p.points = 300
    p.level = 4
    p.is_public_ranking = False
    await db.commit()

    # Oculto inicialmente
    assert user.nickname not in [it["nickname"] for it in (await client.get(RANKING_URL)).json()["items"]]

    # Reactivar visibilidad
    reactivate = await _patch_profile(client, token, {"is_public_ranking": True})
    assert reactivate.status_code == 200
    assert reactivate.json()["profile"]["is_public_ranking"] is True

    # Reaparece en el ranking público con sus puntos
    public_items = (await client.get(RANKING_URL)).json()["items"]
    matching = [it for it in public_items if it["nickname"] == user.nickname]
    assert len(matching) == 1
    assert matching[0]["points"] == 300
    assert matching[0]["level"] == 4


# --- AC-7-8: Posición privada -------------------------------------------------


async def test_ac_7_8_usuario_oculto_consulta_su_posicion_exacta_de_forma_privada(
    client: httpx.AsyncClient,
    student_with_profile: Student,
    make_student: Any,
    complete_diagnostic: Any,
    db: AsyncSession,
) -> None:
    # Crear un segundo estudiante con más puntos
    top_student = await make_student("top.estudiante@correounivalle.edu.co")
    await complete_diagnostic(top_student.token, VALID_DIAGNOSTIC)

    top_profile = await db.get(Profile, top_student.user.id)
    assert top_profile is not None
    top_profile.points = 500
    await db.commit()

    # Nuestro estudiante tiene 200 puntos y está oculto
    my_profile = await db.get(Profile, student_with_profile.user.id)
    assert my_profile is not None
    my_profile.points = 200
    my_profile.is_public_ranking = False
    await db.commit()

    # Consulta privada
    res = await _get_profile(client, student_with_profile.token)
    assert res.status_code == 200
    body = res.json()["profile"]
    assert body["points"] == 200
    assert body["ranking_position"] == 2  # segundo lugar general
    assert body["is_public_ranking"] is False

    # El otro estudiante no puede ver esta información (su consulta devuelve SU perfil)
    top_res = await _get_profile(client, top_student.token)
    assert top_res.status_code == 200
    assert top_res.json()["profile"]["points"] == 500
    assert top_res.json()["profile"]["ranking_position"] == 1


# --- Pruebas complementarias --------------------------------------------------


async def test_usuario_no_autenticado_recibe_401(client: httpx.AsyncClient) -> None:
    assert (await client.get(PROFILE_URL)).status_code == 401
    assert (await client.patch(PROFILE_URL, json={"goal": "strength"})).status_code == 401
    assert (await client.get(MEASUREMENTS_URL)).status_code == 401


async def test_rechaza_campos_no_editables_con_422_not_editable(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    token = student_with_profile.token
    for field in ("points", "level", "ranking_position", "physical_updated_at"):
        res = await _patch_profile(client, token, {field: 123})
        assert res.status_code == 422
        assert any(e["field"] == field and e["code"] == "NOT_EDITABLE" for e in res.json()["error"]["fields"])


async def test_plan_vigente_permanece_intacto_tras_actualizar_perfil_hu7(
    client: httpx.AsyncClient,
    student_with_profile: Student,
    plan_api: Any,
    manual_scheduler: ManualScheduler,
    db: AsyncSession,
) -> None:
    token = student_with_profile.token

    # Generar plan
    assert (await plan_api.generate(token)).status_code == 202
    await manual_scheduler.run_all()

    plan_before = await db.scalar(
        select(WeeklyPlan).where(WeeklyPlan.user_id == student_with_profile.user.id, WeeklyPlan.status == "ready")
    )
    assert plan_before is not None
    plan_id = plan_before.id
    snapshot = plan_before.profile_snapshot

    # Actualizar perfil completo (diagnóstico + peso + estatura + ranking)
    update_res = await _patch_profile(
        client,
        token,
        {
            "goal": "endurance",
            "weight_kg": 74.0,
            "height_cm": 178.0,
            "is_public_ranking": False,
        },
    )
    assert update_res.status_code == 200

    # Comprobar que el plan en BD no cambió en lo absoluto
    plan_after = await db.get(WeeklyPlan, plan_id)
    assert plan_after is not None
    assert plan_after.status == "ready"
    assert plan_after.profile_snapshot == snapshot


async def test_usuarios_nuevos_tienen_is_public_ranking_true_por_defecto(
    client: httpx.AsyncClient, student_with_profile: Student
) -> None:
    res = await _get_profile(client, student_with_profile.token)
    assert res.status_code == 200
    assert res.json()["profile"]["is_public_ranking"] is True
