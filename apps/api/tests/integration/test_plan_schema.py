"""HU 5 - Esquema: CHECK, índices únicos parciales, ai_call_logs sin datos personales y anti-deriva."""
import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.call_log import CALL_STATUSES, AICallLog
from app.ai.use_cases.weekly_plan import rules
from app.modules.plan.models import FAILURE_CODES, PLAN_STATUSES, PlanDay, PlanExercise, WeeklyPlan
from tests.conftest import SeededUser

NOW = datetime(2026, 10, 12, 14, 0, tzinfo=UTC)
MONDAY = date(2026, 10, 12)
SNAPSHOT = {"goal": "strength"}


def _plan(user_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    row = dict(id=uuid.uuid4(), user_id=user_id, week_start=MONDAY, start_date=MONDAY, status="generating",
               generation_number=1, profile_snapshot=SNAPSHOT, created_at=NOW)
    return row | overrides


def _exercise(plan_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    row = dict(id=uuid.uuid4(), plan_id=plan_id, plan_date=MONDAY, position=1, name="Sentadilla", sets=3, reps=10,
               work_seconds=None, rest_seconds=60, requires_machine=False, steps=["Paso uno.", "Paso dos."])
    return row | overrides


async def _insert(db: AsyncSession, model: type, values: dict[str, Any]) -> None:
    savepoint = await db.begin_nested()
    try:
        await db.execute(insert(model).values(**values))
    finally:
        await savepoint.rollback()


async def _ready_plan_with_day(db: AsyncSession, user: SeededUser) -> uuid.UUID:
    plan_id = uuid.uuid4()
    await db.execute(insert(WeeklyPlan).values(**_plan(user.id, id=plan_id, status="ready", ready_at=NOW)))
    await db.execute(insert(PlanDay).values(plan_id=plan_id, plan_date=MONDAY, title="Lunes", estimated_minutes=20))
    return plan_id


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"week_start": date(2026, 10, 13), "start_date": date(2026, 10, 13)}, "ck_weekly_plans_week_start_monday"),
        ({"start_date": date(2026, 10, 17)}, "ck_weekly_plans_start_date"),
        ({"status": "draft"}, "ck_weekly_plans_status"),
        ({"generation_number": 0}, "ck_weekly_plans_generation_number"),
        ({"status": "failed"}, "ck_weekly_plans_failure_iff_failed"),
        ({"failure_code": "AI_UNAVAILABLE"}, "ck_weekly_plans_failure_iff_failed"),
        ({"status": "failed", "failure_code": "OTRO"}, "ck_weekly_plans_failure_code"),
        ({"status": "ready"}, "ck_weekly_plans_ready_iff_ready_at"),
        ({"ready_at": NOW}, "ck_weekly_plans_ready_iff_ready_at"),
    ],
)
async def test_check_de_weekly_plans(db: AsyncSession, verified_user: SeededUser, overrides, constraint: str) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        await _insert(db, WeeklyPlan, _plan(verified_user.id, **overrides))


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"steps": ["Uno."]}, "ck_plan_exercises_steps"),
        ({"steps": ["1", "2", "3", "4", "5"]}, "ck_plan_exercises_steps"),
        ({"steps": "no es arreglo"}, "ck_plan_exercises_steps"),
        ({"sets": 7}, "ck_plan_exercises_sets"),
        ({"sets": 0}, "ck_plan_exercises_sets"),
        ({"reps": 31}, "ck_plan_exercises_reps"),
        ({"reps": None, "work_seconds": 5}, "ck_plan_exercises_work_seconds"),
        ({"rest_seconds": 10}, "ck_plan_exercises_rest_seconds"),
        ({"reps": None, "work_seconds": None}, "ck_plan_exercises_reps_xor_work"),
        ({"reps": 10, "work_seconds": 30}, "ck_plan_exercises_reps_xor_work"),
        ({"plan_date": date(2026, 10, 13)}, "fk_plan_exercises_plan_day"),
    ],
)
async def test_check_de_plan_exercises(db: AsyncSession, verified_user: SeededUser, overrides, constraint: str) -> None:
    plan_id = await _ready_plan_with_day(db, verified_user)

    with pytest.raises(IntegrityError, match=constraint):
        await _insert(db, PlanExercise, _exercise(plan_id, **overrides))


@pytest.mark.parametrize(
    ("values", "constraint"),
    [
        ({"plan_date": date(2026, 10, 17), "title": "Sábado", "estimated_minutes": 20}, "ck_plan_days_weekday"),
        ({"plan_date": date(2026, 10, 13), "title": "", "estimated_minutes": 20}, "ck_plan_days_title"),
        ({"plan_date": date(2026, 10, 13), "title": "Martes", "estimated_minutes": 61}, "ck_plan_days_estimated_minutes"),
    ],
)
async def test_check_de_plan_days(db: AsyncSession, verified_user: SeededUser, values, constraint: str) -> None:
    plan_id = await _ready_plan_with_day(db, verified_user)

    with pytest.raises(IntegrityError, match=constraint):
        await _insert(db, PlanDay, {"plan_id": plan_id, **values})


async def test_indices_unicos_parciales(db: AsyncSession, verified_user: SeededUser) -> None:
    uid = verified_user.id
    await db.execute(insert(WeeklyPlan).values(**_plan(uid, status="ready", ready_at=NOW)))
    await db.execute(insert(WeeklyPlan).values(**_plan(uid)))  # una generación en curso
    await db.execute(insert(WeeklyPlan).values(**_plan(uid, status="failed", failure_code="STALE")))
    await db.execute(insert(WeeklyPlan).values(**_plan(uid, status="failed", failure_code="STALE")))  # varias fallidas: ok
    await db.execute(insert(WeeklyPlan).values(  # ready de OTRA semana: ok
        **_plan(uid, status="ready", ready_at=NOW, week_start=date(2026, 10, 19), start_date=date(2026, 10, 19))
    ))

    with pytest.raises(IntegrityError, match="uq_weekly_plans_ready"):
        await _insert(db, WeeklyPlan, _plan(uid, status="ready", ready_at=NOW))
    with pytest.raises(IntegrityError, match="uq_weekly_plans_generating"):
        await _insert(db, WeeklyPlan, _plan(uid))


async def test_ai_call_logs_no_tiene_user_id_ni_columnas_de_contenido(db: AsyncSession) -> None:
    columns = set((await db.scalars(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'ai_call_logs'"
    ))).all())

    assert columns == {"id", "use_case", "prompt_version", "model", "status", "latency_ms", "attempts", "created_at"}


async def test_cascada_hacia_users_en_tablas_del_plan(db: AsyncSession) -> None:
    rows = (await db.execute(text(
        "SELECT conrelid::regclass::text AS child, confrelid::regclass::text AS parent, confdeltype::text AS d "
        "FROM pg_constraint WHERE contype = 'f' AND conrelid::regclass::text IN "
        "('weekly_plans', 'plan_days', 'plan_exercises')"
    ))).all()

    assert {(r.child, r.parent, r.d) for r in rows} == {
        ("weekly_plans", "users", "c"),
        ("plan_days", "weekly_plans", "c"),
        ("plan_exercises", "plan_days", "c"),
    }


# --- Anti-deriva: constantes del código ↔ CHECK de la migración 0003 ---------------------


async def test_anti_deriva_estados_y_codigos(db: AsyncSession, verified_user: SeededUser) -> None:
    for status in PLAN_STATUSES:
        extra = {"ready": {"ready_at": NOW}, "failed": {"failure_code": "STALE"}}.get(status, {})
        await _insert(db, WeeklyPlan, _plan(verified_user.id, status=status, **extra))
    for code in FAILURE_CODES:
        await _insert(db, WeeklyPlan, _plan(verified_user.id, status="failed", failure_code=code))
    for status in CALL_STATUSES:
        await _insert(db, AICallLog, dict(id=uuid.uuid4(), use_case="weekly_plan", prompt_version="v1", model="m",
                                          status=status, latency_ms=1, attempts=1, created_at=NOW))
    with pytest.raises(IntegrityError, match="ck_ai_call_logs_status"):
        await _insert(db, AICallLog, dict(id=uuid.uuid4(), use_case="x", prompt_version="v1", model="m",
                                          status="otro", latency_ms=1, attempts=1, created_at=NOW))


@pytest.mark.parametrize(
    ("field", "bounds"),
    [
        ("sets", rules.SETS_RANGE),
        ("reps", rules.REPS_RANGE),
        ("rest_seconds", rules.REST_SECONDS_RANGE),
        ("work_seconds", rules.WORK_SECONDS_RANGE),
    ],
)
async def test_anti_deriva_rangos_de_las_reglas(db: AsyncSession, verified_user: SeededUser, field: str, bounds) -> None:
    plan_id = await _ready_plan_with_day(db, verified_user)
    base = {"reps": None} if field == "work_seconds" else {}
    low, high = bounds
    for value in (low, high):
        await _insert(db, PlanExercise, _exercise(plan_id, **base, **{field: value}))
    for value in (low - 1, high + 1):
        with pytest.raises(IntegrityError):
            await _insert(db, PlanExercise, _exercise(plan_id, **base, **{field: value}))


async def test_anti_deriva_numero_de_pasos(db: AsyncSession, verified_user: SeededUser) -> None:
    plan_id = await _ready_plan_with_day(db, verified_user)
    low, high = rules.STEPS_RANGE
    for n in (low, high):
        await _insert(db, PlanExercise, _exercise(plan_id, steps=["Paso."] * n))
    for n in (low - 1, high + 1):
        with pytest.raises(IntegrityError):
            await _insert(db, PlanExercise, _exercise(plan_id, steps=["Paso."] * n))
