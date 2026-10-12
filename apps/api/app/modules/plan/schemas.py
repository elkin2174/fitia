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
