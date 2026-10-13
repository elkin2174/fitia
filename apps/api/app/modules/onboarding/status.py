import uuid
from abc import ABC, abstractmethod

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, get_clock
from app.core.db import get_session
from app.modules.profile.service import ProfileService


class OnboardingStatus(ABC):
    """Puerto: ¿el usuario completó el diagnóstico inicial (HU 4)?"""

    @abstractmethod
    async def is_completed(self, user_id: uuid.UUID) -> bool: ...


class ProfileOnboardingStatus(OnboardingStatus):
    """El diagnóstico está completo si el usuario tiene perfil."""

    def __init__(self, profiles: ProfileService) -> None:
        self._profiles = profiles

    async def is_completed(self, user_id: uuid.UUID) -> bool:
        return await self._profiles.has_profile(user_id)


def get_onboarding_status(
    session: AsyncSession = Depends(get_session), clock: Clock = Depends(get_clock)
) -> OnboardingStatus:
    # Lo usan login (`next`), GET /me (`onboarding_completed`) y require_complete_profile.
    return ProfileOnboardingStatus(ProfileService(session, clock))
