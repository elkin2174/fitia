import logging
import uuid
from typing import Any

from app.core.errors import AppError
from app.modules.profile.schemas import DiagnosticProfile
from app.modules.profile.service import ProfileService
from app.modules.profile.validators import validate_diagnostic, validation_message

logger = logging.getLogger("fitia.onboarding")


class OnboardingService:
    def __init__(self, profiles: ProfileService) -> None:
        self._profiles = profiles

    async def complete(self, user_id: uuid.UUID, raw_answers: Any) -> DiagnosticProfile:
        """Valida el diagnóstico (todos los errores juntos) y delega el guardado en ProfileService."""
        values, errors = validate_diagnostic(raw_answers)
        if errors:
            raise AppError(422, "VALIDATION_ERROR", validation_message(errors), errors)

        profile = await self._profiles.create_from_diagnostic(user_id, DiagnosticProfile(**values))
        # Sin correo ni respuestas: son datos personales de entrenamiento.
        logger.info("diagnostic_completed", extra={"user_id": str(user_id)})
        return profile
