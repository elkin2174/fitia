"""HU 4 - Esquema de perfil: cascada (NFR-12) y CHECK alineados con options.py (anti-deriva)."""
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profile import options
from app.modules.profile.models import Profile, ProfileTrainingDay
from tests.conftest import SeededUser

NOW = datetime(2026, 10, 12, tzinfo=UTC)
BASE_ROW: dict[str, Any] = {
    "goal": "strength",
    "term_weeks": 8,
    "fitness_level": "beginner",
    "session_minutes": 30,
    "has_machine_access": True,
    "created_at": NOW,
    "updated_at": NOW,
}


async def _try_insert(db: AsyncSession, model: type, values: dict[str, Any]) -> None:
    """Inserta dentro de un savepoint y lo revierte siempre (no deja filas)."""
    savepoint = await db.begin_nested()
    try:
        await db.execute(insert(model).values(**values))
    finally:
        await savepoint.rollback()


async def test_tablas_de_perfil_cuelgan_de_users_con_cascade(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            text(
                "SELECT conrelid::regclass::text AS table_name, confdeltype::text AS on_delete "
                "FROM pg_constraint WHERE contype = 'f' AND confrelid = 'public.users'::regclass "
                "AND conrelid::regclass::text IN ('profiles', 'profile_training_days')"
            )
        )
    ).all()

    assert {(r.table_name, r.on_delete) for r in rows} == {("profiles", "c"), ("profile_training_days", "c")}


@pytest.mark.parametrize(
    ("column", "values"),
    [
        ("goal", options.GOALS),
        ("term_weeks", options.TERM_WEEKS),
        ("fitness_level", options.FITNESS_LEVELS),
        ("session_minutes", options.SESSION_MINUTES),
        ("has_machine_access", options.MACHINE_ACCESS),
    ],
)
async def test_anti_deriva_la_bd_acepta_cada_opcion(
    db: AsyncSession, verified_user: SeededUser, column: str, values: tuple
) -> None:
    for value in values:
        await _try_insert(db, Profile, BASE_ROW | {"user_id": verified_user.id, column: value})


async def test_anti_deriva_la_bd_acepta_cada_dia(db: AsyncSession, verified_user: SeededUser) -> None:
    for weekday in options.WEEKDAYS:
        await _try_insert(db, ProfileTrainingDay, {"user_id": verified_user.id, "weekday": weekday})


@pytest.mark.parametrize(
    ("column", "value", "constraint"),
    [
        ("goal", "yoga", "ck_profiles_goal"),
        ("goal", "Strength", "ck_profiles_goal"),
        ("term_weeks", 5, "ck_profiles_term_weeks"),
        ("fitness_level", "pro", "ck_profiles_fitness_level"),
        ("session_minutes", 20, "ck_profiles_session_minutes"),
    ],
)
async def test_check_rechaza_valores_fuera_de_la_lista(
    db: AsyncSession, verified_user: SeededUser, column: str, value: object, constraint: str
) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        await _try_insert(db, Profile, BASE_ROW | {"user_id": verified_user.id, column: value})


@pytest.mark.parametrize("weekday", [0, 6, 7])
async def test_check_rechaza_dias_fuera_de_lunes_a_viernes(
    db: AsyncSession, verified_user: SeededUser, weekday: int
) -> None:
    with pytest.raises(IntegrityError, match="ck_profile_training_days_weekday"):
        await _try_insert(db, ProfileTrainingDay, {"user_id": verified_user.id, "weekday": weekday})


async def test_perfil_exige_un_usuario_existente(db: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="profiles_user_id_fkey"):
        await _try_insert(db, Profile, BASE_ROW | {"user_id": uuid.uuid4()})
