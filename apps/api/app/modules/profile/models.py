import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, SmallInteger, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.profile import options


def _in(column: str, values: tuple[str, ...] | tuple[int, ...]) -> str:
    rendered = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in values)
    return f"{column} IN ({rendered})"


class Profile(Base):
    """Respuestas del diagnóstico inicial y datos vigentes del perfil (HU 4 y HU 7)."""

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(_in("goal", options.GOALS), name="ck_profiles_goal"),
        CheckConstraint(_in("fitness_level", options.FITNESS_LEVELS), name="ck_profiles_fitness_level"),
        CheckConstraint(_in("term_weeks", options.TERM_WEEKS), name="ck_profiles_term_weeks"),
        CheckConstraint(_in("session_minutes", options.SESSION_MINUTES), name="ck_profiles_session_minutes"),
        CheckConstraint(
            f"weight_kg IS NULL OR (weight_kg >= {options.WEIGHT_MIN_KG} AND weight_kg <= {options.WEIGHT_MAX_KG})",
            name="ck_profiles_weight_range",
        ),
        CheckConstraint(
            f"height_cm IS NULL OR (height_cm >= {options.HEIGHT_MIN_CM} AND height_cm <= {options.HEIGHT_MAX_CM})",
            name="ck_profiles_height_range",
        ),
        CheckConstraint("points >= 0", name="ck_profiles_points"),
        CheckConstraint("level >= 1", name="ck_profiles_level"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    term_weeks: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fitness_level: Mapped[str] = mapped_column(Text, nullable=False)
    session_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    has_machine_access: Mapped[bool] = mapped_column(nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    physical_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_public_ranking: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"), default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfileTrainingDay(Base):
    __tablename__ = "profile_training_days"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 5", name="ck_profile_training_days_weekday"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    weekday: Mapped[int] = mapped_column(SmallInteger, primary_key=True)


class PhysicalMeasurement(Base):
    """Historial inmutable de mediciones físicas (peso y estatura) de un estudiante (HU 7)."""

    __tablename__ = "physical_measurements"
    __table_args__ = (
        CheckConstraint(
            f"weight_kg IS NULL OR (weight_kg >= {options.WEIGHT_MIN_KG} AND weight_kg <= {options.WEIGHT_MAX_KG})",
            name="ck_physical_measurements_weight",
        ),
        CheckConstraint(
            f"height_cm IS NULL OR (height_cm >= {options.HEIGHT_MIN_CM} AND height_cm <= {options.HEIGHT_MAX_CM})",
            name="ck_physical_measurements_height",
        ),
        CheckConstraint("weight_kg IS NOT NULL OR height_cm IS NOT NULL", name="ck_physical_measurements_has_value"),
        Index("ix_physical_measurements_user_recorded", "user_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
