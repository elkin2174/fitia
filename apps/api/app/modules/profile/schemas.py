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


class ProfileResponse(BaseModel):
    profile: DiagnosticProfile


class UpdateProfileResponse(BaseModel):
    profile: DiagnosticProfile
    message: str
