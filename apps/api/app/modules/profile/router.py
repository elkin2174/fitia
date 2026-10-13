from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, get_clock
from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser, require_complete_profile
from app.modules.profile.schemas import (
    PhysicalHistoryResponse,
    PhysicalMeasurementOut,
    ProfileResponse,
    PublicRankingResponse,
    UpdateProfileResponse,
)
from app.modules.profile.service import ProfileService

router = APIRouter(prefix="/profile", tags=["Perfil"])
ranking_router = APIRouter(prefix="/ranking", tags=["Ranking"])

_EXAMPLE = {
    "goal": "endurance",
    "term_weeks": 12,
    "fitness_level": "intermediate",
    "session_minutes": 45,
    "training_days": [1, 2, 4],
    "has_machine_access": True,
    "weight_kg": 72.5,
    "height_cm": 175.0,
    "is_public_ranking": True,
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
    """Consulta los datos vigentes del perfil del estudiante autenticado (HU 7).
    Incluye diagnóstico, datos físicos, ranking y puntos acumulados.
    Requiere sesión activa y diagnóstico completado.
    """
    profile = await service.get_profile(user.id)
    assert profile is not None  # require_complete_profile lo garantiza
    return ProfileResponse(profile=profile)


@router.patch("", response_model=UpdateProfileResponse)
async def update_profile(
    payload: Any = Body(default=None, examples=[_EXAMPLE]),
    user: CurrentUser = Depends(require_complete_profile),
    service: ProfileService = Depends(get_profile_service),
) -> UpdateProfileResponse:
    """Actualiza datos del perfil del estudiante autenticado (HU 7).
    Exige sesión, diagnóstico completado y cabecera anti-CSRF X-Requested-With: fitia.
    No regenera ni modifica el plan actual; los cambios aplicarán al próximo plan.
    """
    updated = await service.update_profile(user.id, payload)
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
    """Reemplazo o actualización de datos del perfil (equivalente a PATCH)."""
    return await update_profile(payload=payload, user=user, service=service)


@router.get("/measurements", response_model=PhysicalHistoryResponse)
async def get_physical_measurements_history(
    user: CurrentUser = Depends(require_complete_profile),
    service: ProfileService = Depends(get_profile_service),
) -> PhysicalHistoryResponse:
    """Consulta el historial inmutable de cambios físicos (peso y estatura) del estudiante."""
    records = await service.get_physical_history(user.id)
    return PhysicalHistoryResponse(
        history=[
            PhysicalMeasurementOut(
                id=r.id,
                weight_kg=r.weight_kg,
                height_cm=r.height_cm,
                recorded_at=r.recorded_at,
            )
            for r in records
        ]
    )


@ranking_router.get("", response_model=PublicRankingResponse)
async def get_public_ranking(
    limit: int = 100,
    service: ProfileService = Depends(get_profile_service),
) -> PublicRankingResponse:
    """Consulta el ranking público (HU 32, RANK-1).
    Solo incluye estudiantes con preferencia de visibilidad pública activa.
    """
    items = await service.get_public_ranking(limit=limit)
    return PublicRankingResponse(items=items)
