import uuid
from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.gateway import AIGateway, get_ai_gateway
from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_settings
from app.core.db import get_session, get_session_factory
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.modules.auth.dependencies import CurrentUser, require_complete_profile
from app.modules.plan.runner import PlanGenerationJob, PlanJobScheduler, get_plan_scheduler
from app.modules.plan.schemas import (
    CurrentPlanResponse,
    ExerciseGuideDetailResponse,
    ExerciseGuideOut,
    GeneratePlanResponse,
    NextTrainingDayOut,
    PlanDayDetailOut,
    PlanDayOut,
    PlanExerciseOut,
    PlanFailure,
    TodayPlanResponse,
)
from app.modules.plan.service import PlanService
from app.modules.profile.service import ProfileService

# Solo lectura: no hay PUT, PATCH ni DELETE (AC-5-9, AC-10-4, AC-12-2 / NFR-22).
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


@router.get("/today", response_model=TodayPlanResponse)
async def today(
    user: CurrentUser = Depends(require_complete_profile), service: PlanService = Depends(get_plan_service)
) -> TodayPlanResponse:
    view = await service.today(user.id)
    day_out: PlanDayDetailOut | None = None
    if view.day is not None:
        day_out = PlanDayDetailOut(
            date=view.day.date,
            weekday=view.day.weekday,
            status=view.day.status,
            title=view.day.title,
            estimated_minutes=view.day.estimated_minutes,
            exercises=[
                PlanExerciseOut(
                    id=e.id,
                    position=e.position,
                    name=e.name,
                    sets=e.sets,
                    reps=e.reps,
                    work_seconds=e.work_seconds,
                    rest_seconds=e.rest_seconds,
                    guide=ExerciseGuideOut(steps=e.steps, disclaimer=e.disclaimer),
                )
                for e in view.day.exercises
            ],
        )

    next_day_out: NextTrainingDayOut | None = None
    if view.next_training_day is not None:
        next_day_out = NextTrainingDayOut(
            date=view.next_training_day.date,
            weekday=view.next_training_day.weekday,
            title=view.next_training_day.title,
            planned=view.next_training_day.planned,
        )

    return TodayPlanResponse(
        date=view.date,
        is_weekend=view.is_weekend,
        plan_status=view.plan_status,
        regenerating=view.regenerating,
        failure=PlanFailure(code=view.failure_code) if view.failure_code else None,
        day=day_out,
        next_training_day=next_day_out,
    )


@router.get("/days/{date}", response_model=PlanDayDetailOut)
async def get_day(
    date: date,
    user: CurrentUser = Depends(require_complete_profile),
    service: PlanService = Depends(get_plan_service),
) -> PlanDayDetailOut:
    view = await service.get_day(user.id, date)
    return PlanDayDetailOut(
        date=view.date,
        weekday=view.weekday,
        status=view.status,
        title=view.title,
        estimated_minutes=view.estimated_minutes,
        exercises=[
            PlanExerciseOut(
                id=e.id,
                position=e.position,
                name=e.name,
                sets=e.sets,
                reps=e.reps,
                work_seconds=e.work_seconds,
                rest_seconds=e.rest_seconds,
                guide=ExerciseGuideOut(steps=e.steps, disclaimer=e.disclaimer),
            )
            for e in view.exercises
        ],
    )


@router.get("/exercises/{exercise_id}/guide", response_model=ExerciseGuideDetailResponse)
async def get_exercise_guide(
    exercise_id: uuid.UUID,
    user: CurrentUser = Depends(require_complete_profile),
    service: PlanService = Depends(get_plan_service),
) -> ExerciseGuideDetailResponse:
    view = await service.get_exercise_guide(user.id, exercise_id)
    return ExerciseGuideDetailResponse(
        exercise_id=view.exercise_id,
        name=view.name,
        steps=view.steps,
        disclaimer=view.disclaimer,
    )
