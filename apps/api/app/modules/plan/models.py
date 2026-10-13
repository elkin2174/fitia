import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Estados y códigos de fallo (la migración 0003 los replica literalmente).
STATUS_GENERATING = "generating"
STATUS_READY = "ready"
STATUS_FAILED = "failed"
PLAN_STATUSES: tuple[str, ...] = (STATUS_GENERATING, STATUS_READY, STATUS_FAILED)

FAILURE_AI_UNAVAILABLE = "AI_UNAVAILABLE"
FAILURE_AI_INVALID_OUTPUT = "AI_INVALID_OUTPUT"
FAILURE_GENERATION_TIMEOUT = "GENERATION_TIMEOUT"
FAILURE_STALE = "STALE"
FAILURE_CODES: tuple[str, ...] = (
    FAILURE_AI_UNAVAILABLE,
    FAILURE_AI_INVALID_OUTPUT,
    FAILURE_GENERATION_TIMEOUT,
    FAILURE_STALE,
)

EXERCISE_DISCLAIMER: str = (
    "Esta guía es orientativa y no reemplaza la indicación de un profesional del deporte o de la salud. "
    "Si sientes dolor, detente."
)


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"
    __table_args__ = (
        CheckConstraint("status IN ('generating', 'ready', 'failed')", name="ck_weekly_plans_status"),
        CheckConstraint("extract(isodow FROM week_start) = 1", name="ck_weekly_plans_week_start_monday"),
        CheckConstraint("start_date BETWEEN week_start AND week_start + 4", name="ck_weekly_plans_start_date"),
        CheckConstraint("generation_number >= 1", name="ck_weekly_plans_generation_number"),
        CheckConstraint("(status = 'failed') = (failure_code IS NOT NULL)", name="ck_weekly_plans_failure_iff_failed"),
        CheckConstraint("(status = 'ready') = (ready_at IS NOT NULL)", name="ck_weekly_plans_ready_iff_ready_at"),
        Index("ix_weekly_plans_user_week", "user_id", "week_start"),
        Index(
            "uq_weekly_plans_ready",
            "user_id",
            "week_start",
            unique=True,
            postgresql_where=text("status = 'ready'"),
        ),
        Index("uq_weekly_plans_generating", "user_id", unique=True, postgresql_where=text("status = 'generating'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    generation_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    profile_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanDay(Base):
    """Solo existen filas para los días de entrenamiento."""

    __tablename__ = "plan_days"
    __table_args__ = (
        CheckConstraint("extract(isodow FROM plan_date) BETWEEN 1 AND 5", name="ck_plan_days_weekday"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 60", name="ck_plan_days_title"),
        CheckConstraint("estimated_minutes BETWEEN 1 AND 60", name="ck_plan_days_estimated_minutes"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("weekly_plans.id", ondelete="CASCADE"), primary_key=True
    )
    plan_date: Mapped[date] = mapped_column(Date, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class PlanExercise(Base):
    __tablename__ = "plan_exercises"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_date"],
            ["plan_days.plan_id", "plan_days.plan_date"],
            ondelete="CASCADE",
            name="fk_plan_exercises_plan_day",
        ),
        UniqueConstraint("plan_id", "plan_date", "position", name="uq_plan_exercises_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sets: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reps: Mapped[int | None] = mapped_column(SmallInteger)
    work_seconds: Mapped[int | None] = mapped_column(SmallInteger)
    rest_seconds: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    requires_machine: Mapped[bool] = mapped_column(nullable=False)
    steps: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
