"""HU 5 - Generación del plan: AC-5-1 a AC-5-4, AC-5-7, regeneración, rate limit, seguridad y NFR-12."""
import asyncio
import uuid
from datetime import date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters.fake_text import FakeTextAdapter, Fail
from app.ai.use_cases.weekly_plan.rules import MACHINE_TERMS, contains_term, day_seconds, minutes
from app.core.clock import BOGOTA_TZ, FrozenClock
from app.core.config import Settings
from app.modules.plan.models import PlanDay, PlanExercise, WeeklyPlan
from tests.conftest import VALID_DIAGNOSTIC, Student, with_session
from tests.fakes import ManualScheduler

MONDAY = date(2026, 10, 12)


async def _ready_plan(db: AsyncSession, student: Student) -> WeeklyPlan:
    plan = await db.scalar(
        select(WeeklyPlan).where(WeeklyPlan.user_id == student.user.id, WeeklyPlan.status == "ready")
    )
    assert plan is not None
    return plan


async def _generate_ready(plan_api, manual_scheduler: ManualScheduler, token: str) -> str:
    response = await plan_api.generate(token)
    assert response.status_code == 202, response.text
    await manual_scheduler.run_all()
    return response.json()["plan_id"]


async def _student_with_days(student: Student, complete_diagnostic, **answers: Any) -> Student:
    response = await complete_diagnostic(student.token, VALID_DIAGNOSTIC | answers)
    assert response.status_code == 201
    return student


async def _change_profile(db: AsyncSession, student: Student, goal: str) -> None:
    """Simula la edición del perfil (el PATCH /profile llega con la HU 6)."""
    await db.execute(text("UPDATE profiles SET goal = :g WHERE user_id = :id"), {"g": goal, "id": student.user.id})
    await db.commit()


# --- AC-5-1: generar y ver la semana ----------------------------------------------------


async def test_ac_5_1_generar_muestra_la_semana_con_la_rutina_de_cada_dia(
    plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student, db: AsyncSession, fake_ai: FakeTextAdapter
) -> None:
    token = student_with_profile.token
    started = await plan_api.generate(token)

    assert started.status_code == 202
    assert started.json()["status"] == "generating"
    assert started.headers["Cache-Control"] == "no-store"
    plan_id = started.json()["plan_id"]

    during = await plan_api.current(token)
    assert during.json()["status"] == "generating"
    assert fake_ai.calls == 0

    await manual_scheduler.run_all()
    ready = await plan_api.current(token)

    assert ready.status_code == 200
    assert ready.headers["Cache-Control"] == "no-store"
    body = ready.json()
    assert body["status"] == "ready" and body["generation_number"] == 1
    assert body["failure"] is None and not body["outdated"] and not body["regenerating"]
    training = [d for d in body["days"] if d["status"] == "training"]
    assert [d["weekday"] for d in training] == [1, 3, 5]
    assert all(d["title"] and 1 <= d["estimated_minutes"] <= 30 for d in training)

    plan = await _ready_plan(db, student_with_profile)
    assert str(plan.id) == plan_id
    assert plan.prompt_version == "v1"
    assert plan.profile_snapshot == VALID_DIAGNOSTIC | {"training_days": [1, 3, 5]}
    log = (await db.execute(text("SELECT * FROM ai_call_logs"))).mappings().all()
    assert [(row["status"], row["use_case"], row["attempts"]) for row in log] == [("ok", "weekly_plan", 1)]
    assert "user_id" not in log[0]


async def test_status_none_antes_de_generar(plan_api, student_with_profile: Student) -> None:
    body = (await plan_api.current(student_with_profile.token)).json()

    assert body["status"] == "none" and body["generation_number"] == 0
    assert [d["status"] for d in body["days"]] == ["unplanned"] * 5
    assert all(d["title"] is None for d in body["days"])
    assert body["week_start"] == body["start_date"] == MONDAY.isoformat()


# --- AC-5-2: solo los días elegidos tienen rutina ----------------------------------------


@pytest.mark.parametrize(
    ("today", "expected_week", "expected_days"),
    [
        (MONDAY, MONDAY, ["training", "rest", "training", "rest", "training"]),
        (MONDAY + timedelta(days=2), MONDAY, ["unplanned", "unplanned", "training", "rest", "training"]),
        (MONDAY + timedelta(days=5), MONDAY + timedelta(days=7), ["training", "rest", "training", "rest", "training"]),
        (MONDAY + timedelta(days=6), MONDAY + timedelta(days=7), ["training", "rest", "training", "rest", "training"]),
    ],
    ids=["lunes", "miercoles", "sabado", "domingo"],
)
async def test_ac_5_2_solo_los_dias_elegidos_tienen_rutina(
    plan_api, manual_scheduler, student_with_profile: Student, clock: FrozenClock,
    today: date, expected_week: date, expected_days: list[str],
) -> None:
    clock.set(datetime.combine(today, datetime.min.time(), tzinfo=BOGOTA_TZ).replace(hour=10))

    await _generate_ready(plan_api, manual_scheduler, student_with_profile.token)
    body = (await plan_api.current(student_with_profile.token)).json()

    assert body["week_start"] == expected_week.isoformat()
    assert [d["status"] for d in body["days"]] == expected_days
    assert [d["date"] for d in body["days"]] == [(expected_week + timedelta(days=i)).isoformat() for i in range(5)]
    for day in body["days"]:
        assert (day["title"] is not None) == (day["status"] == "training")


async def test_ac_5_2_viernes_sin_dias_restantes_da_plan_vacio_sin_llamar_a_la_ia(
    plan_api, manual_scheduler, student: Student, complete_diagnostic, clock: FrozenClock,
    db: AsyncSession, fake_ai: FakeTextAdapter,
) -> None:
    await _student_with_days(student, complete_diagnostic, training_days=[1, 2])
    clock.set(datetime(2026, 10, 16, 9, 0, tzinfo=BOGOTA_TZ))  # viernes

    await _generate_ready(plan_api, manual_scheduler, student.token)
    body = (await plan_api.current(student.token)).json()

    assert fake_ai.calls == 0
    assert body["status"] == "ready"
    assert [d["status"] for d in body["days"]] == ["unplanned"] * 4 + ["rest"]
    plan = await _ready_plan(db, student)
    assert plan.prompt_version is None
    assert await db.scalar(select(func.count()).select_from(PlanDay)) == 0


# --- AC-5-3 y AC-5-4: tiempo, máquinas y ejercicios completos -----------------------------


@pytest.mark.parametrize("session_minutes", [15, 30, 45, 60])
@pytest.mark.parametrize("has_machine_access", [True, False])
async def test_ac_5_3_ninguna_sesion_supera_el_tiempo_ni_usa_maquinas_sin_acceso(
    plan_api, manual_scheduler, student: Student, complete_diagnostic, db: AsyncSession,
    session_minutes: int, has_machine_access: bool,
) -> None:
    await _student_with_days(
        student, complete_diagnostic, session_minutes=session_minutes,
        has_machine_access=has_machine_access, training_days=[1, 2, 3, 4, 5],
    )
    await _generate_ready(plan_api, manual_scheduler, student.token)
    plan = await _ready_plan(db, student)

    days = (await db.scalars(select(PlanDay).where(PlanDay.plan_id == plan.id))).all()
    assert len(days) == 5
    for day in days:
        exercises = (await db.scalars(
            select(PlanExercise).where(PlanExercise.plan_id == plan.id, PlanExercise.plan_date == day.plan_date)
        )).all()
        recomputed = minutes(day_seconds([(e.sets, e.reps, e.work_seconds, e.rest_seconds) for e in exercises]))
        assert day.estimated_minutes == recomputed <= session_minutes
        if not has_machine_access:
            for ex in exercises:
                assert not ex.requires_machine
                assert contains_term(" ".join([ex.name, *ex.steps]), MACHINE_TERMS) is None


async def test_ac_5_4_cada_ejercicio_trae_series_repeticiones_descanso_y_explicacion(
    plan_api, manual_scheduler, student_with_profile: Student, db: AsyncSession
) -> None:
    await _generate_ready(plan_api, manual_scheduler, student_with_profile.token)

    exercises = (await db.scalars(select(PlanExercise))).all()
    assert exercises
    for ex in exercises:
        assert ex.name.strip()
        assert 1 <= ex.sets <= 6
        assert (ex.reps is None) != (ex.work_seconds is None)
        assert 15 <= ex.rest_seconds <= 180
        assert isinstance(ex.steps, list) and 2 <= len(ex.steps) <= 4
        assert all(isinstance(s, str) and s.strip() for s in ex.steps)
    positions = {}
    for ex in exercises:
        positions.setdefault(ex.plan_date, []).append(ex.position)
    assert all(sorted(p) == list(range(1, len(p) + 1)) for p in positions.values())


# --- AC-5-7: sin duplicados -------------------------------------------------------------


async def test_ac_5_7_dos_post_seguidos_devuelven_la_misma_generacion(
    plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student, db: AsyncSession, fake_ai: FakeTextAdapter
) -> None:
    first = await plan_api.generate(student_with_profile.token)
    second = await plan_api.generate(student_with_profile.token)

    assert first.status_code == second.status_code == 202
    assert first.json()["plan_id"] == second.json()["plan_id"]
    assert await db.scalar(select(func.count()).select_from(WeeklyPlan)) == 1
    assert manual_scheduler.pending == 1
    await manual_scheduler.run_all()
    assert fake_ai.calls == 1


async def test_ac_5_7_dos_post_simultaneos_crean_una_sola_generacion(
    plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student, db: AsyncSession
) -> None:
    responses = await asyncio.gather(*(plan_api.generate(student_with_profile.token) for _ in range(3)))

    assert {r.status_code for r in responses} == {202}
    assert len({r.json()["plan_id"] for r in responses}) == 1
    assert await db.scalar(select(func.count()).select_from(WeeklyPlan)) == 1
    assert manual_scheduler.pending == 1


async def test_ac_5_7_con_plan_vigente_y_diagnostico_igual_responde_409(
    plan_api, manual_scheduler, student_with_profile: Student, db: AsyncSession
) -> None:
    await _generate_ready(plan_api, manual_scheduler, student_with_profile.token)

    response = await plan_api.generate(student_with_profile.token)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PLAN_UP_TO_DATE"
    assert await db.scalar(select(func.count()).select_from(WeeklyPlan)) == 1
    assert manual_scheduler.pending == 0


# --- Regeneración -------------------------------------------------------------------------


async def test_regeneracion_reemplaza_el_plan_anterior(
    plan_api, manual_scheduler, student_with_profile: Student, db: AsyncSession, plan_footprint
) -> None:
    token = student_with_profile.token
    old_plan_id = await _generate_ready(plan_api, manual_scheduler, token)
    await _change_profile(db, student_with_profile, "endurance")

    outdated = (await plan_api.current(token)).json()
    assert outdated["outdated"] is True and outdated["can_regenerate"] is True

    started = await plan_api.generate(token)
    assert started.status_code == 202
    regenerating = (await plan_api.current(token)).json()
    assert regenerating["status"] == "ready" and regenerating["regenerating"] is True
    assert regenerating["can_regenerate"] is False
    await manual_scheduler.run_all()

    body = (await plan_api.current(token)).json()
    assert body["generation_number"] == 2 and body["outdated"] is False
    plans = (await db.scalars(select(WeeklyPlan))).all()
    assert [(str(p.id), p.status) for p in plans] == [(started.json()["plan_id"], "ready")]
    assert await db.scalar(
        select(func.count()).select_from(PlanDay).where(PlanDay.plan_id == uuid.UUID(old_plan_id))
    ) == 0
    assert (await plan_footprint(student_with_profile.user.id))["weekly_plans"] == 1


async def test_regeneracion_tiene_limite_semanal(
    plan_api, manual_scheduler, student_with_profile: Student, db: AsyncSession, settings: Settings
) -> None:
    settings.PLAN_MAX_GENERATIONS_PER_WEEK = 2
    token = student_with_profile.token
    await _generate_ready(plan_api, manual_scheduler, token)
    await _change_profile(db, student_with_profile, "endurance")
    await _generate_ready(plan_api, manual_scheduler, token)
    await _change_profile(db, student_with_profile, "weight_loss")

    assert (await plan_api.current(token)).json()["can_regenerate"] is False
    response = await plan_api.generate(token)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "REGENERATION_LIMIT"
    assert int(response.headers["Retry-After"]) > 0
    assert manual_scheduler.pending == 0


async def test_un_intento_fallido_no_consume_el_limite_semanal(
    plan_api, manual_scheduler, student_with_profile: Student, db: AsyncSession, settings: Settings,
    fake_ai: FakeTextAdapter,
) -> None:
    settings.PLAN_MAX_GENERATIONS_PER_WEEK = 2
    token = student_with_profile.token
    await _generate_ready(plan_api, manual_scheduler, token)
    await _change_profile(db, student_with_profile, "endurance")
    fake_ai.script(Fail("server_error"), Fail("server_error"))
    await _generate_ready(plan_api, manual_scheduler, token)
    assert (await plan_api.current(token)).json()["failure"] == {"code": "AI_UNAVAILABLE"}

    await _generate_ready(plan_api, manual_scheduler, token)

    body = (await plan_api.current(token)).json()
    assert body["status"] == "ready" and body["generation_number"] == 2 and body["failure"] is None


# --- Rate limit ---------------------------------------------------------------------------


async def test_rate_limit_por_usuario(
    plan_api, manual_scheduler, student_with_profile: Student, settings: Settings, fake_ai: FakeTextAdapter
) -> None:
    settings.RATE_LIMIT_PLAN_GENERATE_PER_USER = 2
    token = student_with_profile.token
    fake_ai.script(*[Fail("server_error")] * 4)
    for _ in range(2):
        assert (await plan_api.generate(token)).status_code == 202
        assert (await plan_api.generate(token)).status_code == 202  # idempotente: no consume cupo
        await manual_scheduler.run_all()

    response = await plan_api.generate(token)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert int(response.headers["Retry-After"]) > 0


async def test_los_409_no_consumen_cupo(
    plan_api, manual_scheduler, student_with_profile: Student, settings: Settings
) -> None:
    settings.RATE_LIMIT_PLAN_GENERATE_PER_USER = 1
    await _generate_ready(plan_api, manual_scheduler, student_with_profile.token)

    statuses = [(await plan_api.generate(student_with_profile.token)).status_code for _ in range(3)]

    assert statuses == [409, 409, 409]


# --- Seguridad (NFR-10) -------------------------------------------------------------------


async def test_sin_sesion_devuelve_401(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/v1/plan/generate")).status_code == 401
    assert (await client.get("/api/v1/plan/current")).status_code == 401


async def test_sin_perfil_devuelve_403_onboarding_required(plan_api, student: Student) -> None:
    for response in (await plan_api.generate(student.token), await plan_api.current(student.token)):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ONBOARDING_REQUIRED"


async def test_sin_encabezado_csrf_devuelve_403(
    client: httpx.AsyncClient, student_with_profile: Student, db: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/plan/generate", headers={**with_session(student_with_profile.token), "X-Requested-With": ""}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_HEADER_MISSING"
    assert await db.scalar(select(func.count()).select_from(WeeklyPlan)) == 0


async def test_nfr_10_un_usuario_no_ve_ni_toca_el_plan_de_otro(
    plan_api, manual_scheduler, student_with_profile: Student, make_student, complete_diagnostic, plan_footprint
) -> None:
    await _generate_ready(plan_api, manual_scheduler, student_with_profile.token)
    a_before = await plan_footprint(student_with_profile.user.id)
    other = await make_student("otro.estudiante@correounivalle.edu.co")
    await complete_diagnostic(other.token)

    assert (await plan_api.current(other.token)).json()["status"] == "none"
    body = {"user_id": str(student_with_profile.user.id), "plan_id": str(uuid.uuid4())}
    response = await plan_api.generate(other.token, json=body)
    await manual_scheduler.run_all()

    assert response.status_code == 202
    assert await plan_footprint(student_with_profile.user.id) == a_before
    assert (await plan_footprint(other.user.id))["weekly_plans"] == 1


# --- NFR-12: eliminación de cuenta --------------------------------------------------------


async def test_nfr_12_eliminar_la_cuenta_borra_plan_dias_y_ejercicios(
    client: httpx.AsyncClient, plan_api, manual_scheduler, student_with_profile: Student, plan_footprint, db: AsyncSession
) -> None:
    await _generate_ready(plan_api, manual_scheduler, student_with_profile.token)
    plan_ids = (await db.scalars(select(WeeklyPlan.id))).all()
    assert (await plan_footprint(student_with_profile.user.id))["plan_exercises"] > 0

    deleted = await client.post(
        "/api/v1/me/delete-account", json={"confirm": True}, headers=with_session(student_with_profile.token)
    )

    assert deleted.status_code == 204
    assert await plan_footprint(student_with_profile.user.id) == {"weekly_plans": 0, "plan_days": 0, "plan_exercises": 0}
    for table in ("plan_days", "plan_exercises"):
        count = await db.scalar(text(f"SELECT count(*) FROM {table} WHERE plan_id = ANY(:ids)"), {"ids": list(plan_ids)})
        assert count == 0


async def test_nfr_12_eliminar_la_cuenta_con_la_generacion_pendiente_termina_en_silencio(
    client: httpx.AsyncClient, plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student,
    db: AsyncSession, caplog: pytest.LogCaptureFixture,
) -> None:
    await plan_api.generate(student_with_profile.token)
    await client.post(
        "/api/v1/me/delete-account", json={"confirm": True}, headers=with_session(student_with_profile.token)
    )

    await manual_scheduler.run_all()  # no lanza

    for table in ("weekly_plans", "plan_days", "plan_exercises"):
        assert await db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    assert "plan_generation_error" not in caplog.text
