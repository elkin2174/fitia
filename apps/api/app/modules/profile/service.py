import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.errors import AppError
from app.modules.profile.models import Profile
from app.modules.profile.repository import ProfileRepository
from app.modules.profile.schemas import DiagnosticProfile

_PROFILE_PK_CONSTRAINT = "profiles_pkey"


def _is_profile_pk_violation(exc: IntegrityError) -> bool:
    cause = getattr(exc.orig, "__cause__", None)
    constraint = getattr(cause, "constraint_name", None) or getattr(exc.orig, "constraint_name", None)
    return constraint == _PROFILE_PK_CONSTRAINT or _PROFILE_PK_CONSTRAINT in str(exc.orig)


class ProfileService:
    """Dueño de los datos del perfil. Otros módulos lo usan a él, nunca al repositorio (ADR-01)."""

    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._repo = ProfileRepository(session)
        self._clock = clock

    async def has_profile(self, user_id: uuid.UUID) -> bool:
        return await self._repo.exists(user_id)

    async def create_from_diagnostic(self, user_id: uuid.UUID, answers: DiagnosticProfile) -> DiagnosticProfile:
        """Guarda perfil y días en UNA transacción. 409 si el usuario ya tiene perfil."""
        if await self._repo.exists(user_id):
            raise self._profile_exists_error()

        now = self._clock.now()
        try:
            await self._repo.add_profile(
                Profile(
                    user_id=user_id,
                    goal=answers.goal,
                    term_weeks=answers.term_weeks,
                    fitness_level=answers.fitness_level,
                    session_minutes=answers.session_minutes,
                    has_machine_access=answers.has_machine_access,
                    created_at=now,
                    updated_at=now,
                )
            )
            await self._repo.add_training_days(user_id, answers.training_days)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if _is_profile_pk_violation(exc):  # otra petición simultánea lo creó primero
                raise self._profile_exists_error() from None
            raise
        except Exception:
            await self._session.rollback()  # nunca queda un perfil sin días
            raise
        return answers

    @staticmethod
    def _profile_exists_error() -> AppError:
        return AppError(
            409,
            "PROFILE_EXISTS",
            "Ya completaste tu diagnóstico inicial. Puedes cambiar tus datos desde tu perfil.",
        )
