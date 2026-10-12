import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.profile import options


def _in(column: str, values: tuple[str, ...] | tuple[int, ...]) -> str:
    rendered = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in values)
    return f"{column} IN ({rendered})"


class Profile(Base):
    """Respuestas del diagnóstico inicial (HU 4). Una fila por usuario."""

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(_in("goal", options.GOALS), name="ck_profiles_goal"),
        CheckConstraint(_in("fitness_level", options.FITNESS_LEVELS), name="ck_profiles_fitness_level"),
        CheckConstraint(_in("term_weeks", options.TERM_WEEKS), name="ck_profiles_term_weeks"),
        CheckConstraint(_in("session_minutes", options.SESSION_MINUTES), name="ck_profiles_session_minutes"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    term_weeks: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fitness_level: Mapped[str] = mapped_column(Text, nullable=False)
    session_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    has_machine_access: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfileTrainingDay(Base):
    __tablename__ = "profile_training_days"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 5", name="ck_profile_training_days_weekday"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    weekday: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
