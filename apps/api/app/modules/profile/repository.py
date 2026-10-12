import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profile.models import Profile, ProfileTrainingDay


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
