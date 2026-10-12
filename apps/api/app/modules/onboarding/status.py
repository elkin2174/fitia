import uuid
from abc import ABC, abstractmethod


class OnboardingStatus(ABC):
    """Puerto: ¿el usuario completó el diagnóstico inicial (HU 4)?"""

    @abstractmethod
    async def is_completed(self, user_id: uuid.UUID) -> bool: ...


class PendingOnboardingStatus(OnboardingStatus):
    """Implementación provisional mientras no exista la tabla `profiles`: nadie lo ha completado."""

    async def is_completed(self, user_id: uuid.UUID) -> bool:
        return False


_default_status = PendingOnboardingStatus()


def get_onboarding_status() -> OnboardingStatus:
    # PUNTO DE REEMPLAZO (HU 4): devolver una implementación que consulte `profiles`, p. ej.
    #   def get_onboarding_status(session: AsyncSession = Depends(get_session)) -> OnboardingStatus:
    #       return ProfileOnboardingStatus(session)
    return _default_status
