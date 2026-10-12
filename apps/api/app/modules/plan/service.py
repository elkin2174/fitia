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
from app.modules.plan.calendar import CalendarDay, date_for, target_week, week_days
from app.modules.plan.models import STATUS_GENERATING, PlanDay, WeeklyPlan
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
