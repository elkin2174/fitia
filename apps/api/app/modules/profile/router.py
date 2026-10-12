from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, get_clock
from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser, require_complete_profile
from app.modules.profile.schemas import ProfileResponse, UpdateProfileResponse
from app.modules.profile.service import ProfileService

router = APIRouter(prefix="/profile", tags=["Perfil"])

_EXAMPLE = {
    "goal": "endurance",
    "term_weeks": 12,
    "fitness_level": "intermediate",
    "session_minutes": 45,
    "training_days": [1, 2, 4],
    "has_machine_access": True,
}


def get_profile_service(
    session: AsyncSession = Depends(get_session), clock: Clock = Depends(get_clock)
) -> ProfileService:
    return ProfileService(session, clock)


@router.get("", response_model=ProfileResponse)
async def get_profile(
    user: CurrentUser = Depends(require_complete_profile),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    """Consulta las respuestas vigentes del diagnóstico del estudiante autenticado (HU 6).
    Requiere sesión activa y haber completado el diagnóstico inicial (S+P).
    """
    profile = await service.get_diagnostic(user.id)
    assert profile is not None  # require_complete_profile lo garantiza
    return ProfileResponse(profile=profile)


@router.patch("", response_model=UpdateProfileResponse)
async def update_profile(
    payload: Any = Body(default=None, examples=[_EXAMPLE]),
    user: CurrentUser = Depends(require_complete_profile),
    service: ProfileService = Depends(get_profile_service),
) -> UpdateProfileResponse:
    """Actualiza las respuestas del diagnóstico del estudiante autenticado (HU 6).
    Exige sesión, diagnóstico completado (S+P) y cabecera anti-CSRF X-Requested-With: fitia.
    No regenera ni modifica el plan actual; los cambios aplicarán al próximo plan.
    """
    updated = await service.update_diagnostic(user.id, payload)
    return UpdateProfileResponse(
        profile=updated,
        message=(
            "Tu diagnóstico se actualizó correctamente. Los cambios se aplicarán "
            "al próximo plan que generes. Tu plan actual no ha cambiado."
        ),
    )


@router.put("", response_model=UpdateProfileResponse)
async def replace_profile(
    payload: Any = Body(default=None, examples=[_EXAMPLE]),
    user: CurrentUser = Depends(require_complete_profile),
    service: ProfileService = Depends(get_profile_service),
) -> UpdateProfileResponse:
    """Reemplazo o actualización de respuestas del diagnóstico (equivalente a PATCH)."""
    return await update_profile(payload=payload, user=user, service=service)
