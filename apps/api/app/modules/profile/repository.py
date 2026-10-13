import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.profile.models import PhysicalMeasurement, Profile, ProfileTrainingDay


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, user_id: uuid.UUID) -> bool:
        return bool(await self._session.scalar(select(exists().where(Profile.user_id == user_id))))

    async def get(self, user_id: uuid.UUID) -> Profile | None:
        return await self._session.get(Profile, user_id)

    async def get_training_days(self, user_id: uuid.UUID) -> list[int]:
        result = await self._session.scalars(
            select(ProfileTrainingDay.weekday)
            .where(ProfileTrainingDay.user_id == user_id)
            .order_by(ProfileTrainingDay.weekday)
        )
        return list(result.all())

    async def add_profile(self, profile: Profile) -> None:
        self._session.add(profile)
        await self._session.flush()

    async def add_training_days(self, user_id: uuid.UUID, weekdays: Iterable[int]) -> None:
        self._session.add_all(ProfileTrainingDay(user_id=user_id, weekday=day) for day in weekdays)
        await self._session.flush()

    async def update_profile(self, user_id: uuid.UUID, values: dict[str, Any], updated_at: datetime) -> None:
        scalar_fields = {k: v for k, v in values.items() if k != "training_days"}
        stmt = (
            update(Profile)
            .where(Profile.user_id == user_id)
            .values(**scalar_fields, updated_at=updated_at)
        )
        await self._session.execute(stmt)

    async def replace_training_days(self, user_id: uuid.UUID, weekdays: Iterable[int]) -> None:
        await self._session.execute(delete(ProfileTrainingDay).where(ProfileTrainingDay.user_id == user_id))
        self._session.add_all(ProfileTrainingDay(user_id=user_id, weekday=day) for day in weekdays)
        await self._session.flush()

    async def add_physical_measurement(self, measurement: PhysicalMeasurement) -> None:
        self._session.add(measurement)
        await self._session.flush()

    async def get_physical_measurements(self, user_id: uuid.UUID) -> list[PhysicalMeasurement]:
        result = await self._session.scalars(
            select(PhysicalMeasurement)
            .where(PhysicalMeasurement.user_id == user_id)
            .order_by(PhysicalMeasurement.recorded_at.desc())
        )
        return list(result.all())

    async def get_ranking_position(self, user_id: uuid.UUID) -> int | None:
        """Calcula la posición exacta del usuario en el ranking general (incluso si está oculto)."""
        subq = (
            select(
                Profile.user_id,
                func.row_number()
                .over(order_by=(Profile.points.desc(), Profile.created_at.asc()))
                .label("rank"),
            )
        ).subquery()
        stmt = select(subq.c.rank).where(subq.c.user_id == user_id)
        return await self._session.scalar(stmt)

    async def get_public_ranking(self, limit: int = 100) -> list[tuple[int, str, int, int]]:
        """Devuelve el ranking público ordenado: solo usuarios visibles (HU32, RANK-1)."""
        subq = (
            select(
                Profile.user_id,
                User.nickname,
                Profile.points,
                Profile.level,
                func.row_number()
                .over(order_by=(Profile.points.desc(), Profile.created_at.asc()))
                .label("pos"),
            )
            .join(User, User.id == Profile.user_id)
            .where(Profile.is_public_ranking.is_(True))
        ).subquery()
        stmt = (
            select(subq.c.pos, subq.c.nickname, subq.c.points, subq.c.level)
            .order_by(subq.c.pos.asc())
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        return [(r.pos, r.nickname, r.points, r.level) for r in rows.all()]
