import logging
import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.errors import AppError, FieldError
from app.modules.profile.models import PhysicalMeasurement, Profile
from app.modules.profile.repository import ProfileRepository
from app.modules.profile.schemas import DiagnosticProfile, RankingItem, StudentProfile
from app.modules.profile.validators import (
    validate_diagnostic,
    validate_profile_update,
    validation_message,
)

logger = logging.getLogger("fitia.profile")

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

    async def get_diagnostic(self, user_id: uuid.UUID) -> DiagnosticProfile | None:
        """Las 6 respuestas del diagnóstico (días ordenados), o None si no hay perfil."""
        profile = await self._repo.get(user_id)
        if profile is None:
            return None
        return DiagnosticProfile(
            goal=profile.goal,
            term_weeks=profile.term_weeks,
            fitness_level=profile.fitness_level,
            session_minutes=profile.session_minutes,
            training_days=await self._repo.get_training_days(user_id),
            has_machine_access=profile.has_machine_access,
        )

    async def get_profile(self, user_id: uuid.UUID) -> StudentProfile | None:
        """Perfil completo del estudiante (HU 7): diagnóstico + datos físicos + ranking privado."""
        profile = await self._repo.get(user_id)
        if profile is None:
            return None
        training_days = await self._repo.get_training_days(user_id)
        ranking_pos = await self._repo.get_ranking_position(user_id)
        return StudentProfile(
            goal=profile.goal,
            term_weeks=profile.term_weeks,
            fitness_level=profile.fitness_level,
            session_minutes=profile.session_minutes,
            training_days=training_days,
            has_machine_access=profile.has_machine_access,
            weight_kg=profile.weight_kg,
            height_cm=profile.height_cm,
            physical_updated_at=profile.physical_updated_at,
            is_public_ranking=profile.is_public_ranking,
            points=profile.points,
            level=profile.level,
            ranking_position=ranking_pos,
        )

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

    async def update_diagnostic(self, user_id: uuid.UUID, raw_answers: Any) -> DiagnosticProfile:
        """Actualiza las respuestas del diagnóstico en UNA transacción (HU 6).
        Valida que el perfil exista (404 si no) y que los datos sean válidos (422 si no).
        Si no hay cambios frente al perfil actual, evita escrituras innecesarias.
        """
        current = await self.get_diagnostic(user_id)
        if current is None:
            raise AppError(404, "PROFILE_NOT_FOUND", "No se encontró el perfil del estudiante.")

        values, errors = validate_diagnostic(raw_answers, partial=True)
        if errors:
            raise AppError(422, "VALIDATION_ERROR", validation_message(errors), errors)
        if not values:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Debes incluir al menos un campo del diagnóstico para actualizar.",
                [FieldError("body", "EMPTY_UPDATE")],
            )

        # Evitar escrituras innecesarias si los valores son idénticos a los actuales
        changed = any(getattr(current, k) != v for k, v in values.items())
        if not changed:
            return current

        now = self._clock.now()
        try:
            await self._repo.update_profile(user_id, values, now)
            if "training_days" in values:
                await self._repo.replace_training_days(user_id, values["training_days"])
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        logger.info(
            "profile_updated",
            extra={"user_id": str(user_id), "fields": sorted(list(values.keys()))},
        )
        updated = await self.get_diagnostic(user_id)
        assert updated is not None
        return updated

    async def update_profile(self, user_id: uuid.UUID, raw_payload: Any) -> StudentProfile:
        """Actualiza cualquier dato editable del perfil en UNA transacción (HU 7).
        Valida que el perfil exista (404 si no), rechaza campos no editables (422),
        valida tipos estrictos y opciones de opciones cerradas.
        Registra mediciones físicas en el historial si peso o estatura cambian.
        Si no hay cambios frente al perfil actual, evita escrituras innecesarias.
        """
        current = await self.get_profile(user_id)
        if current is None:
            raise AppError(404, "PROFILE_NOT_FOUND", "No se encontró el perfil del estudiante.")

        values, errors = validate_profile_update(raw_payload)
        if errors:
            raise AppError(422, "VALIDATION_ERROR", validation_message(errors), errors)
        if not values:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Debes incluir al menos un campo del perfil para actualizar.",
                [FieldError("body", "EMPTY_UPDATE")],
            )

        # Comprobar si realmente hubo cambios
        changed = False
        for k, v in values.items():
            if getattr(current, k) != v:
                changed = True
                break

        if not changed:
            return current

        now = self._clock.now()
        try:
            # Si se actualizó peso o estatura, agregar medición al historial inmutable
            physical_changed = (
                ("weight_kg" in values and values["weight_kg"] != current.weight_kg)
                or ("height_cm" in values and values["height_cm"] != current.height_cm)
            )
            if physical_changed:
                new_weight = values.get("weight_kg", current.weight_kg)
                new_height = values.get("height_cm", current.height_cm)
                await self._repo.add_physical_measurement(
                    PhysicalMeasurement(
                        user_id=user_id,
                        weight_kg=new_weight,
                        height_cm=new_height,
                        recorded_at=now,
                    )
                )
                values["physical_updated_at"] = now

            await self._repo.update_profile(user_id, values, now)
            if "training_days" in values:
                await self._repo.replace_training_days(user_id, values["training_days"])
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        logger.info(
            "profile_updated",
            extra={"user_id": str(user_id), "fields": sorted(list(values.keys()))},
        )
        updated = await self.get_profile(user_id)
        assert updated is not None
        return updated

    async def get_public_ranking(self, limit: int = 100) -> list[RankingItem]:
        """Obtiene el ranking público ordenado (HU32, RANK-1).
        Excluye a usuarios que tengan is_public_ranking = False.
        """
        rows = await self._repo.get_public_ranking(limit=limit)
        return [RankingItem(position=pos, nickname=nick, points=pts, level=lvl) for pos, nick, pts, lvl in rows]

    async def get_physical_history(self, user_id: uuid.UUID) -> list[PhysicalMeasurement]:
        """Consulta el historial de mediciones físicas del estudiante."""
        return await self._repo.get_physical_measurements(user_id)

    @staticmethod
    def _profile_exists_error() -> AppError:
        return AppError(
            409,
            "PROFILE_EXISTS",
            "Ya completaste tu diagnóstico inicial. Puedes cambiar tus datos desde tu perfil.",
        )
