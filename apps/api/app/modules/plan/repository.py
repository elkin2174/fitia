import uuid
from datetime import date, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.plan.models import (
    FAILURE_STALE,
    STATUS_FAILED,
    STATUS_GENERATING,
    STATUS_READY,
    PlanDay,
    PlanExercise,
    WeeklyPlan,
)


class PlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, plan_id: uuid.UUID) -> WeeklyPlan | None:
        return await self._session.get(WeeklyPlan, plan_id)

    async def mark_stale(self, user_id: uuid.UUID, created_before: datetime) -> None:
        """Generaciones huérfanas (p. ej. reinicio de la instancia) → failed STALE."""
        await self._session.execute(
            update(WeeklyPlan)
            .where(
                WeeklyPlan.user_id == user_id,
                WeeklyPlan.status == STATUS_GENERATING,
                WeeklyPlan.created_at <= created_before,
            )
            .values(status=STATUS_FAILED, failure_code=FAILURE_STALE)
        )

    async def get_generating(self, user_id: uuid.UUID) -> WeeklyPlan | None:
        return await self._session.scalar(
            select(WeeklyPlan).where(WeeklyPlan.user_id == user_id, WeeklyPlan.status == STATUS_GENERATING)
        )

    async def get_ready(self, user_id: uuid.UUID, week_start: date) -> WeeklyPlan | None:
        return await self._session.scalar(
            select(WeeklyPlan).where(
                WeeklyPlan.user_id == user_id,
                WeeklyPlan.week_start == week_start,
                WeeklyPlan.status == STATUS_READY,
            )
        )

    async def get_latest_failed(self, user_id: uuid.UUID) -> WeeklyPlan | None:
        return await self._session.scalar(
            select(WeeklyPlan)
            .where(WeeklyPlan.user_id == user_id, WeeklyPlan.status == STATUS_FAILED)
            .order_by(WeeklyPlan.created_at.desc())
            .limit(1)
        )

    async def get_days(self, plan_id: uuid.UUID) -> list[PlanDay]:
        result = await self._session.scalars(
            select(PlanDay).where(PlanDay.plan_id == plan_id).order_by(PlanDay.plan_date)
        )
        return list(result.all())

    async def delete_failed(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(WeeklyPlan).where(WeeklyPlan.user_id == user_id, WeeklyPlan.status == STATUS_FAILED)
        )

    async def add_plan(self, plan: WeeklyPlan) -> None:
        self._session.add(plan)
        await self._session.flush()

    async def delete_other_ready(self, user_id: uuid.UUID, week_start: date, keep_id: uuid.UUID) -> None:
        """Regeneración: el plan anterior de la semana se borra (el cascade borra días y ejercicios)."""
        await self._session.execute(
            delete(WeeklyPlan).where(
                WeeklyPlan.user_id == user_id,
                WeeklyPlan.week_start == week_start,
                WeeklyPlan.status == STATUS_READY,
                WeeklyPlan.id != keep_id,
            )
        )

    async def mark_ready(self, plan_id: uuid.UUID, ready_at: datetime, prompt_version: str | None) -> bool:
        """Solo si sigue en `generating`; False si la fila ya no existe o fue marcada STALE."""
        result = await self._session.execute(
            update(WeeklyPlan)
            .where(WeeklyPlan.id == plan_id, WeeklyPlan.status == STATUS_GENERATING)
            .values(status=STATUS_READY, ready_at=ready_at, prompt_version=prompt_version)
            .returning(WeeklyPlan.id)
        )
        return result.first() is not None

    async def mark_failed(self, plan_id: uuid.UUID, failure_code: str) -> bool:
        result = await self._session.execute(
            update(WeeklyPlan)
            .where(WeeklyPlan.id == plan_id, WeeklyPlan.status == STATUS_GENERATING)
            .values(status=STATUS_FAILED, failure_code=failure_code)
            .returning(WeeklyPlan.id)
        )
        return result.first() is not None

    async def add_day(self, day: PlanDay) -> None:
        self._session.add(day)
        await self._session.flush()

    async def add_exercise(self, exercise: PlanExercise) -> None:
        self._session.add(exercise)
        await self._session.flush()

    async def get_day_with_exercises(
        self, plan_id: uuid.UUID, plan_date: date
    ) -> tuple[PlanDay | None, list[PlanExercise]]:
        day = await self._session.scalar(
            select(PlanDay).where(PlanDay.plan_id == plan_id, PlanDay.plan_date == plan_date)
        )
        if day is None:
            return None, []
        result = await self._session.scalars(
            select(PlanExercise)
            .where(PlanExercise.plan_id == plan_id, PlanExercise.plan_date == plan_date)
            .order_by(PlanExercise.position)
        )
        return day, list(result.all())

    async def get_exercise_guide(
        self, user_id: uuid.UUID, week_start: date, exercise_id: uuid.UUID
    ) -> PlanExercise | None:
        return await self._session.scalar(
            select(PlanExercise)
            .join(WeeklyPlan, WeeklyPlan.id == PlanExercise.plan_id)
            .where(
                PlanExercise.id == exercise_id,
                WeeklyPlan.user_id == user_id,
                WeeklyPlan.week_start == week_start,
                WeeklyPlan.status == STATUS_READY,
            )
        )
