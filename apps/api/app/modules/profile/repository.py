import uuid
from collections.abc import Iterable

from sqlalchemy import exists, select
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
