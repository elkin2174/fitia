"""Generación del plan en segundo plano (ADR-09).

La tarea NO mantiene conexión ni transacción abierta mientras espera a la IA: lee en una sesión
corta, la cierra, llama al gateway y guarda en otra transacción corta y atómica.
"""
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.errors import AIFailure
from app.ai.gateway import AIGateway
from app.ai.privacy import WeeklyPlanInput
from app.ai.use_cases.weekly_plan.rules import ValidatedPlan
from app.ai.use_cases.weekly_plan.use_case import WEEKLY_PLAN
from app.core.clock import Clock
from app.modules.plan.calendar import date_for, remaining_training_days
from app.modules.plan.models import FAILURE_AI_UNAVAILABLE, STATUS_GENERATING, PlanDay, PlanExercise
from app.modules.plan.repository import PlanRepository

logger = logging.getLogger("fitia.plan")

Job = Callable[[], Awaitable[None]]


class PlanJobScheduler(ABC):
    @abstractmethod
    def schedule(self, job: Job) -> None: ...


class BackgroundTasksScheduler(PlanJobScheduler):
    """Implementación real: se ejecuta después de enviar la respuesta (NFR-06)."""

    def __init__(self, background: BackgroundTasks) -> None:
        self._background = background

    def schedule(self, job: Job) -> None:
        # Envoltorio `async def` a propósito: Starlette decide con is_async_callable() si espera la tarea;
        # una lambda que devuelve una corrutina iría a un threadpool y la corrutina nunca se ejecutaría.
        self._background.add_task(_await_job, job)


async def _await_job(job: Job) -> None:
    await job()


def get_plan_scheduler(background: BackgroundTasks) -> PlanJobScheduler:
    return BackgroundTasksScheduler(background)


@dataclass(frozen=True)
class _PendingPlan:
    user_id: uuid.UUID
    week_start: date
    start_date: date
    snapshot: dict[str, Any]


class PlanGenerationJob:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], gateway: AIGateway, clock: Clock
    ) -> None:
        self._session_factory = session_factory
        self._gateway = gateway
        self._clock = clock

    async def run(self, plan_id: uuid.UUID) -> None:
        """Nunca lanza y nunca deja la fila en `generating`."""
        try:
            await self._run(plan_id)
        except Exception as exc:  # noqa: BLE001 - error interno inesperado (p. ej. de BD al guardar)
            logger.error("plan_generation_error", extra={"plan_id": str(plan_id), "error_type": type(exc).__name__})
            await self._fail(plan_id, FAILURE_AI_UNAVAILABLE, attempts=0, latency_ms=0)

    async def _run(self, plan_id: uuid.UUID) -> None:
        pending = await self._load(plan_id)
        if pending is None:  # cuenta eliminada, marcada STALE o ya resuelta: no hay nada que hacer
            return

        snapshot = pending.snapshot
        days = remaining_training_days(snapshot["training_days"], pending.week_start, pending.start_date)
        if not days:
            # Plan vacío: no quedan días de entrenamiento esta semana; no se llama a la IA.
            await self._save(plan_id, pending, None, prompt_version=None, attempts=0, latency_ms=0)
            return

        plan_input = WeeklyPlanInput(**{**snapshot, "training_days": days})
        try:
            result = await self._gateway.run(WEEKLY_PLAN, plan_input)
        except AIFailure as failure:
            await self._fail(plan_id, failure.code, attempts=failure.attempts, latency_ms=failure.latency_ms)
            return
        await self._save(
            plan_id, pending, result.value, prompt_version=result.prompt_version,
            attempts=result.attempts, latency_ms=result.latency_ms,
        )

    async def _load(self, plan_id: uuid.UUID) -> _PendingPlan | None:
        async with self._session_factory() as session:
            plan = await PlanRepository(session).get(plan_id)
            if plan is None or plan.status != STATUS_GENERATING:
                return None
            return _PendingPlan(plan.user_id, plan.week_start, plan.start_date, dict(plan.profile_snapshot))

    async def _save(
        self,
        plan_id: uuid.UUID,
        pending: _PendingPlan,
        plan: ValidatedPlan | None,
        *,
        prompt_version: str | None,
        attempts: int,
        latency_ms: int,
    ) -> None:
        """UNA transacción: el plan se guarda completo o no se guarda."""
        async with self._session_factory() as session:
            repo = PlanRepository(session)
            await repo.delete_other_ready(pending.user_id, pending.week_start, plan_id)
            if not await repo.mark_ready(plan_id, self._clock.now(), prompt_version):
                # Cuenta eliminada durante la generación o fila marcada STALE: se descarta en silencio.
                await session.rollback()
                return
            for day in plan.days if plan else ():
                plan_date = date_for(pending.week_start, day.weekday)
                await repo.add_day(
                    PlanDay(plan_id=plan_id, plan_date=plan_date, title=day.title, estimated_minutes=day.estimated_minutes)
                )
                for ex in day.exercises:
                    await repo.add_exercise(
                        PlanExercise(
                            plan_id=plan_id,
                            plan_date=plan_date,
                            position=ex.position,
                            name=ex.name,
                            sets=ex.sets,
                            reps=ex.reps,
                            work_seconds=ex.work_seconds,
                            rest_seconds=ex.rest_seconds,
                            requires_machine=ex.requires_machine,
                            steps=list(ex.steps),
                        )
                    )
            await repo.delete_failed(pending.user_id)
            await session.commit()
        logger.info(
            "plan_generated", extra={"plan_id": str(plan_id), "attempts": attempts, "latency_ms": latency_ms}
        )

    async def _fail(self, plan_id: uuid.UUID, code: str, *, attempts: int, latency_ms: int) -> None:
        try:
            async with self._session_factory() as session:
                failed = await PlanRepository(session).mark_failed(plan_id, code)
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("plan_mark_failed_error", extra={"plan_id": str(plan_id), "error_type": type(exc).__name__})
            return
        if failed:
            logger.info(
                "plan_generation_failed",
                extra={"plan_id": str(plan_id), "failure_code": code, "attempts": attempts, "latency_ms": latency_ms},
            )
