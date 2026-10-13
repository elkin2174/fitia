from typing import Any

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, get_clock
from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser, get_current_user
from app.modules.onboarding.questionnaire import QUESTIONNAIRE
from app.modules.onboarding.schemas import CompleteDiagnosticResponse, QuestionnaireResponse
from app.modules.onboarding.service import OnboardingService
from app.modules.profile.service import ProfileService

router = APIRouter(prefix="/onboarding", tags=["Diagnóstico inicial"])

_EXAMPLE = {
    "goal": "strength",
    "term_weeks": 8,
    "fitness_level": "beginner",
    "session_minutes": 30,
    "training_days": [1, 3, 5],
    "has_machine_access": True,
}


def get_onboarding_service(
    session: AsyncSession = Depends(get_session), clock: Clock = Depends(get_clock)
) -> OnboardingService:
    return OnboardingService(ProfileService(session, clock))


# Ambos endpoints usan get_current_user y NO require_complete_profile: quien aún no tiene perfil debe poder usarlos.
@router.get("/questionnaire", response_model=QuestionnaireResponse)
async def questionnaire(_: CurrentUser = Depends(get_current_user)) -> QuestionnaireResponse:
    return QUESTIONNAIRE


@router.post("/complete", status_code=status.HTTP_201_CREATED, response_model=CompleteDiagnosticResponse)
async def complete(
    # Cualquier JSON: el servicio valida campo por campo y devuelve todos los faltantes juntos.
    payload: Any = Body(default=None, examples=[_EXAMPLE]),
    user: CurrentUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> CompleteDiagnosticResponse:
    # NFR-10: el perfil se crea para el usuario de la sesión; un user_id en el cuerpo se ignora.
    return CompleteDiagnosticResponse(profile=await service.complete(user.id, payload))
