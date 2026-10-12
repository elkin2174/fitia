"""Salida esperada de la IA. Tipado estricto (un bool no es un entero; sin números como texto).
Las claves desconocidas se ignoran y nunca se guardan."""
from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")


class ExerciseOut(_Strict):
    name: str
    sets: int
    reps: int | None = None
    work_seconds: int | None = None
    rest_seconds: int
    requires_machine: bool
    steps: list[str]


class DayOut(_Strict):
    weekday: int
    title: str
    estimated_minutes: int | None = None  # informativo: el servidor recalcula la duración
    exercises: list[ExerciseOut]


class WeeklyPlanOutput(_Strict):
    days: list[DayOut]
