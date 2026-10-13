import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.profile import options

# Literal[(…)] equivale a Literal[a, b, …]: el OpenAPI publica los enums desde options.py.
Goal = Literal[options.GOALS]  # type: ignore[valid-type]
TermWeeks = Literal[options.TERM_WEEKS]  # type: ignore[valid-type]
FitnessLevel = Literal[options.FITNESS_LEVELS]  # type: ignore[valid-type]
SessionMinutes = Literal[options.SESSION_MINUTES]  # type: ignore[valid-type]
Weekday = Literal[options.WEEKDAYS]  # type: ignore[valid-type]


class DiagnosticProfile(BaseModel):
    """Exactamente los 6 datos del diagnóstico. Es la forma pública del perfil (HU 4 y HU 6)
    y la base de la allowlist de datos que la HU 5 podrá enviar a la IA."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    goal: Goal
    term_weeks: TermWeeks
    fitness_level: FitnessLevel
    session_minutes: SessionMinutes
    training_days: list[Weekday]
    has_machine_access: bool


class StudentProfile(BaseModel):
    """Perfil completo del estudiante (HU 7): diagnóstico + datos físicos + ranking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    goal: Goal
    term_weeks: TermWeeks
    fitness_level: FitnessLevel
    session_minutes: SessionMinutes
    training_days: list[Weekday]
    has_machine_access: bool
    weight_kg: float | None = None
    height_cm: float | None = None
    physical_updated_at: datetime | None = None
    is_public_ranking: bool = True
    points: int = 0
    level: int = 1
    ranking_position: int | None = None


class ProfileResponse(BaseModel):
    profile: StudentProfile


class UpdateProfileResponse(BaseModel):
    profile: StudentProfile
    message: str


class RankingItem(BaseModel):
    position: int
    nickname: str
    points: int
    level: int


class PublicRankingResponse(BaseModel):
    items: list[RankingItem]


class PhysicalMeasurementOut(BaseModel):
    id: uuid.UUID
    weight_kg: float | None
    height_cm: float | None
    recorded_at: datetime


class PhysicalHistoryResponse(BaseModel):
    history: list[PhysicalMeasurementOut]
