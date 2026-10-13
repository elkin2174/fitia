import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import BOGOTA_TZ, Clock
from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import RateLimiter
from app.modules.plan.calendar import (
    CalendarDay,
    NextTrainingDayView,
    date_for,
    find_next_training_day,
    target_week,
    week_days,
)
from app.modules.plan.models import (
    EXERCISE_DISCLAIMER,
    STATUS_GENERATING,
    STATUS_READY,
    PlanDay,
    PlanExercise,
    WeeklyPlan,
)
from app.modules.plan.repository import PlanRepository
from app.modules.plan.runner import PlanGenerationJob, PlanJobScheduler
from app.modules.profile.schemas import DiagnosticProfile
from app.modules.profile.service import ProfileService

logger = logging.getLogger("fitia.plan")

_GENERATING_UNIQUE_INDEX = "uq_weekly_plans_generating"


@dataclass(frozen=True)
class PlanDayView:
    day: CalendarDay
    title: str | None = None
    estimated_minutes: int | None = None


@dataclass(frozen=True)
class CurrentPlanView:
    status: str
    regenerating: bool
    week_start: date
    start_date: date
    generation_number: int
    outdated: bool
    can_regenerate: bool
    failure_code: str | None
    days: list[PlanDayView]


@dataclass(frozen=True)
class PlanExerciseView:
    id: uuid.UUID
    position: int
    name: str
    sets: int
    reps: int | None
    work_seconds: int | None
    rest_seconds: int
    steps: list[str]
    disclaimer: str


@dataclass(frozen=True)
class PlanDayDetailView:
    date: date
    weekday: int
    status: str
    title: str | None
    estimated_minutes: int | None
    exercises: list[PlanExerciseView]


@dataclass(frozen=True)
class TodayPlanView:
    date: date
    is_weekend: bool
    plan_status: str
    regenerating: bool
    failure_code: str | None
    day: PlanDayDetailView | None
    next_training_day: NextTrainingDayView | None


@dataclass(frozen=True)
class ExerciseGuideDetailView:
    exercise_id: uuid.UUID
    name: str
    steps: list[str]
    disclaimer: str


def _exercise_view(ex: PlanExercise) -> PlanExerciseView:
    return PlanExerciseView(
        id=ex.id,
        position=ex.position,
        name=ex.name,
        sets=ex.sets,
        reps=ex.reps,
        work_seconds=ex.work_seconds,
        rest_seconds=ex.rest_seconds,
        steps=list(ex.steps),
        disclaimer=EXERCISE_DISCLAIMER,
    )


def _snapshot(diagnostic: DiagnosticProfile) -> dict[str, object]:
    return diagnostic.model_dump(mode="json")


def _is_generating_conflict(exc: IntegrityError) -> bool:
    return _GENERATING_UNIQUE_INDEX in str(exc.orig)


class PlanService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        clock: Clock,
        profiles: ProfileService,
        limiter: RateLimiter,
        scheduler: PlanJobScheduler,
        job: PlanGenerationJob,
    ) -> None:
        self._session = session
        self._repo = PlanRepository(session)
        self._settings = settings
        self._clock = clock
        self._profiles = profiles
        self._limiter = limiter
        self._scheduler = scheduler
        self._job = job

    async def _expire_stale(self, user_id: uuid.UUID) -> None:
        threshold = self._clock.now() - timedelta(seconds=self._settings.PLAN_STALE_SECONDS)
        await self._repo.mark_stale(user_id, threshold)
        await self._session.commit()

    async def _diagnostic(self, user_id: uuid.UUID) -> DiagnosticProfile:
        diagnostic = await self._profiles.get_diagnostic(user_id)
        assert diagnostic is not None  # garantizado por require_complete_profile
        return diagnostic

    async def generate(self, user_id: uuid.UUID) -> uuid.UUID:
        await self._expire_stale(user_id)

        # Idempotencia: doble clic o reintento mientras se genera → misma generación, sin costo.
        in_progress = await self._repo.get_generating(user_id)
        if in_progress is not None:
            return in_progress.id

        diagnostic = await self._diagnostic(user_id)
        snapshot = _snapshot(diagnostic)
        week_start, start_date = target_week(self._clock.today_date())
        ready = await self._repo.get_ready(user_id, week_start)
        if ready is None:
            generation_number = 1
        elif ready.profile_snapshot == snapshot:
            raise AppError(409, "PLAN_UP_TO_DATE", "Ya tienes un plan generado para esta semana con tu diagnóstico actual.")
        elif ready.generation_number >= self._settings.PLAN_MAX_GENERATIONS_PER_WEEK:
            raise AppError(
                429,
                "REGENERATION_LIMIT",
                "Ya regeneraste tu plan el máximo de veces esta semana. Podrás generar uno nuevo la próxima semana.",
                headers={"Retry-After": str(self._seconds_until(week_start + timedelta(days=7)))},
            )
        else:
            generation_number = ready.generation_number + 1

        # Solo las generaciones que de verdad empiezan consumen cupo.
        window = self._settings.RATE_LIMIT_PLAN_GENERATE_WINDOW_MINUTES * 60
        self._limiter.hit(f"plan:generate:{user_id}", self._settings.RATE_LIMIT_PLAN_GENERATE_PER_USER, window)

        plan = WeeklyPlan(
            id=uuid.uuid4(),
            user_id=user_id,
            week_start=week_start,
            start_date=start_date,
            status=STATUS_GENERATING,
            generation_number=generation_number,
            profile_snapshot=snapshot,  # las 6 respuestas completas, sin filtrar
            created_at=self._clock.now(),
        )
        try:
            await self._repo.delete_failed(user_id)
            await self._repo.add_plan(plan)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if not _is_generating_conflict(exc):
                raise
            # Otra petición simultánea ganó: se devuelve su generación (nunca dos ni un 500).
            winner = await self._repo.get_generating(user_id)
            if winner is None:
                raise
            return winner.id

        logger.info(
            "plan_generation_started",
            extra={"plan_id": str(plan.id), "generation_number": generation_number},
        )
        plan_id = plan.id
        self._scheduler.schedule(lambda: self._job.run(plan_id))
        return plan_id

    async def current(self, user_id: uuid.UUID) -> CurrentPlanView:
        """Solo lee la BD: nunca llama a la IA (NFR-16)."""
        await self._expire_stale(user_id)
        diagnostic = await self._diagnostic(user_id)
        week_start, start_date = target_week(self._clock.today_date())

        ready = await self._repo.get_ready(user_id, week_start)
        generating = await self._repo.get_generating(user_id)
        failed = await self._repo.get_latest_failed(user_id)

        if ready is not None:
            status = "ready"
        elif generating is not None:
            status = "generating"
        elif failed is not None:
            status = "failed"
        else:
            status = "none"

        outdated = ready is not None and ready.profile_snapshot != _snapshot(diagnostic)
        can_regenerate = (
            outdated
            and ready is not None
            and ready.generation_number < self._settings.PLAN_MAX_GENERATIONS_PER_WEEK
            and generating is None
        )
        if ready is not None:
            start_date = ready.start_date
            days = self._ready_days(ready, await self._repo.get_days(ready.id))
        else:
            days = [
                PlanDayView(CalendarDay(date=date_for(week_start, wd), weekday=wd, status="unplanned"))
                for wd in range(1, 6)
            ]

        return CurrentPlanView(
            status=status,
            regenerating=ready is not None and generating is not None,
            week_start=week_start,
            start_date=start_date,
            generation_number=ready.generation_number if ready else 0,
            outdated=outdated,
            can_regenerate=can_regenerate,
            failure_code=failed.failure_code if failed else None,
            days=days,
        )

    @staticmethod
    def _ready_days(plan: WeeklyPlan, plan_days: list[PlanDay]) -> list[PlanDayView]:
        by_date = {d.plan_date: d for d in plan_days}
        views = []
        for day in week_days(plan.week_start, plan.start_date, set(by_date)):
            stored = by_date.get(day.date)
            views.append(
                PlanDayView(day, title=stored.title, estimated_minutes=stored.estimated_minutes)
                if stored
                else PlanDayView(day)
            )
        return views

    def _seconds_until(self, day: date) -> int:
        target = datetime.combine(day, time.min, tzinfo=BOGOTA_TZ)
        return max(1, int((target - self._clock.now()).total_seconds()))

    async def today(self, user_id: uuid.UUID) -> TodayPlanView:
        await self._expire_stale(user_id)
        diagnostic = await self._diagnostic(user_id)
        today = self._clock.today_date()
        weekday = today.isoweekday()
        is_weekend = weekday > 5
        week_start, start_date = target_week(today)

        ready = await self._repo.get_ready(user_id, week_start)
        generating = await self._repo.get_generating(user_id)
        failed = await self._repo.get_latest_failed(user_id)

        if ready is not None:
            plan_status = "ready"
        elif generating is not None:
            plan_status = "generating"
        elif failed is not None:
            plan_status = "failed"
        else:
            plan_status = "none"

        regenerating = ready is not None and generating is not None
        failure_code = failed.failure_code if failed else None

        day_view: PlanDayDetailView | None = None
        if ready is not None and not is_weekend:
            day_obj, exercises = await self._repo.get_day_with_exercises(ready.id, today)
            if day_obj is not None:
                day_view = PlanDayDetailView(
                    date=today,
                    weekday=weekday,
                    status="training",
                    title=day_obj.title,
                    estimated_minutes=day_obj.estimated_minutes,
                    exercises=[_exercise_view(e) for e in exercises],
                )
            else:
                status = "rest" if today >= ready.start_date else "unplanned"
                day_view = PlanDayDetailView(
                    date=today,
                    weekday=weekday,
                    status=status,
                    title=None,
                    estimated_minutes=None,
                    exercises=[],
                )

        next_training_day: NextTrainingDayView | None = None
        if day_view is None or day_view.status != "training":
            if is_weekend:
                ready_days = await self._repo.get_days(ready.id) if ready else None
                next_training_day = find_next_training_day(
                    today=today,
                    target_week_start=week_start,
                    current_plan_days=ready_days,
                    next_week_plan_days=None,
                    profile_training_weekdays=diagnostic.training_days,
                )
            else:
                current_plan_days = await self._repo.get_days(ready.id) if ready else None
                next_week_start = week_start + timedelta(days=7)
                next_week_ready = await self._repo.get_ready(user_id, next_week_start)
                next_week_days = await self._repo.get_days(next_week_ready.id) if next_week_ready else None
                next_training_day = find_next_training_day(
                    today=today,
                    target_week_start=week_start,
                    current_plan_days=current_plan_days,
                    next_week_plan_days=next_week_days,
                    profile_training_weekdays=diagnostic.training_days,
                )

        return TodayPlanView(
            date=today,
            is_weekend=is_weekend,
            plan_status=plan_status,
            regenerating=regenerating,
            failure_code=failure_code,
            day=day_view,
            next_training_day=next_training_day,
        )

    async def get_day(self, user_id: uuid.UUID, target_date: date) -> PlanDayDetailView:
        await self._expire_stale(user_id)
        today = self._clock.today_date()
        week_start, _ = target_week(today)

        if (
            target_date < week_start
            or target_date > week_start + timedelta(days=4)
            or target_date.isoweekday() > 5
        ):
            raise AppError(404, "PLAN_DAY_NOT_FOUND", "El día solicitado no pertenece a la semana activa.")

        ready = await self._repo.get_ready(user_id, week_start)
        if ready is None:
            raise AppError(404, "PLAN_NOT_FOUND", "No tienes un plan vigente para esta semana.")

        day_obj, exercises = await self._repo.get_day_with_exercises(ready.id, target_date)
        if day_obj is not None:
            return PlanDayDetailView(
                date=target_date,
                weekday=target_date.isoweekday(),
                status="training",
                title=day_obj.title,
                estimated_minutes=day_obj.estimated_minutes,
                exercises=[_exercise_view(e) for e in exercises],
            )

        status = "rest" if target_date >= ready.start_date else "unplanned"
        return PlanDayDetailView(
            date=target_date,
            weekday=target_date.isoweekday(),
            status=status,
            title=None,
            estimated_minutes=None,
            exercises=[],
        )

    async def get_exercise_guide(
        self, user_id: uuid.UUID, exercise_id: uuid.UUID
    ) -> ExerciseGuideDetailView:
        await self._expire_stale(user_id)
        today = self._clock.today_date()
        week_start, _ = target_week(today)

        exercise = await self._repo.get_exercise_guide(user_id, week_start, exercise_id)
        if exercise is None:
            raise AppError(404, "EXERCISE_NOT_FOUND", "No se encontró el ejercicio solicitado en tu plan vigente.")

        return ExerciseGuideDetailView(
            exercise_id=exercise.id,
            name=exercise.name,
            steps=list(exercise.steps),
            disclaimer=EXERCISE_DISCLAIMER,
        )
