import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel


class GeneratePlanResponse(BaseModel):
    plan_id: uuid.UUID
    status: Literal["generating"] = "generating"


class PlanFailure(BaseModel):
    code: str


class PlanDayOut(BaseModel):
    date: date
    weekday: int
    status: Literal["training", "rest", "unplanned", "completed"]
    title: str | None = None
    estimated_minutes: int | None = None


class CurrentPlanResponse(BaseModel):
    status: Literal["none", "generating", "ready", "failed"]
    regenerating: bool
    week_start: date
    start_date: date
    generation_number: int
    outdated: bool
    can_regenerate: bool
    failure: PlanFailure | None
    days: list[PlanDayOut]


class ExerciseGuideOut(BaseModel):
    steps: list[str]
    disclaimer: str


class PlanExerciseOut(BaseModel):
    id: uuid.UUID
    position: int
    name: str
    sets: int
    reps: int | None = None
    work_seconds: int | None = None
    rest_seconds: int
    guide: ExerciseGuideOut


class PlanDayDetailOut(BaseModel):
    date: date
    weekday: int
    status: Literal["training", "rest", "unplanned", "completed"]
    title: str | None = None
    estimated_minutes: int | None = None
    exercises: list[PlanExerciseOut] = []


class NextTrainingDayOut(BaseModel):
    date: date
    weekday: int
    title: str | None = None
    planned: bool


class TodayPlanResponse(BaseModel):
    date: date
    is_weekend: bool
    plan_status: Literal["none", "generating", "ready", "failed"]
    regenerating: bool
    failure: PlanFailure | None = None
    day: PlanDayDetailOut | None = None
    next_training_day: NextTrainingDayOut | None = None


class ExerciseGuideDetailResponse(BaseModel):
    exercise_id: uuid.UUID
    name: str
    steps: list[str]
    disclaimer: str
