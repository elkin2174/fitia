from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.gateway import AIGateway, get_ai_gateway
from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_settings
from app.core.db import get_session, get_session_factory
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.modules.auth.dependencies import CurrentUser, require_complete_profile
from app.modules.plan.runner import PlanGenerationJob, PlanJobScheduler, get_plan_scheduler
from app.modules.plan.schemas import CurrentPlanResponse, GeneratePlanResponse, PlanDayOut, PlanFailure
from app.modules.plan.service import PlanService
from app.modules.profile.service import ProfileService

# Solo dos operaciones: el plan es de solo lectura (AC-5-9 / NFR-22). No hay PUT, PATCH ni DELETE.
router = APIRouter(prefix="/plan", tags=["Plan semanal"])


def get_plan_job(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    gateway: AIGateway = Depends(get_ai_gateway),
    clock: Clock = Depends(get_clock),
) -> PlanGenerationJob:
    return PlanGenerationJob(session_factory, gateway, clock)


def get_plan_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
    limiter: RateLimiter = Depends(get_rate_limiter),
    scheduler: PlanJobScheduler = Depends(get_plan_scheduler),
    job: PlanGenerationJob = Depends(get_plan_job),
) -> PlanService:
    return PlanService(session, settings, clock, ProfileService(session, clock), limiter, scheduler, job)


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED, response_model=GeneratePlanResponse)
async def generate(
    user: CurrentUser = Depends(require_complete_profile), service: PlanService = Depends(get_plan_service)
) -> GeneratePlanResponse:
    # El cuerpo se ignora: todo sale del perfil guardado y el usuario, de la sesión (NFR-10).
    return GeneratePlanResponse(plan_id=await service.generate(user.id))


@router.get("/current", response_model=CurrentPlanResponse)
async def current(
    user: CurrentUser = Depends(require_complete_profile), service: PlanService = Depends(get_plan_service)
) -> CurrentPlanResponse:
    view = await service.current(user.id)
    return CurrentPlanResponse(
        status=view.status,
        regenerating=view.regenerating,
        week_start=view.week_start,
        start_date=view.start_date,
        generation_number=view.generation_number,
        outdated=view.outdated,
        can_regenerate=view.can_regenerate,
        failure=PlanFailure(code=view.failure_code) if view.failure_code else None,
        days=[
            PlanDayOut(
                date=d.day.date,
                weekday=d.day.weekday,
                status=d.day.status,
                title=d.title,
                estimated_minutes=d.estimated_minutes,
            )
            for d in view.days
        ],
    )
