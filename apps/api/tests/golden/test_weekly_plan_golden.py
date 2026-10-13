"""Casos golden del plan semanal con el adaptador falso: entrada → propiedades esperadas.

Con Gemini real, los mismos casos se ejecutan a mano con scripts/smoke_gemini.py.
"""
import json
from pathlib import Path

import pytest

from app.ai.adapters.fake_text import FakeTextAdapter
from app.ai.call_log import MemoryCallRecorder
from app.ai.gateway import AIGateway
from app.ai.privacy import WeeklyPlanInput
from app.ai.resilience import CircuitBreaker
from app.ai.use_cases.weekly_plan.rules import MACHINE_TERMS, contains_term
from app.ai.use_cases.weekly_plan.use_case import WEEKLY_PLAN
from app.core.clock import FrozenClock
from app.core.config import Settings

CASES = sorted((Path(__file__).parent / "weekly_plan").glob("*.json"))


def test_hay_al_menos_cuatro_casos() -> None:
    assert len(CASES) >= 4


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
async def test_golden(path: Path) -> None:
    case = json.loads(path.read_text(encoding="utf-8"))
    plan_input = WeeklyPlanInput(**case["input"])
    expect = case["expect"]
    gateway = AIGateway(Settings(_env_file=None), FakeTextAdapter(), CircuitBreaker(5, 60, 30),
                        MemoryCallRecorder(), FrozenClock())

    plan = (await gateway.run(WEEKLY_PLAN, plan_input)).value

    assert [d.weekday for d in plan.days] == expect["weekdays"]
    exercises = [ex for d in plan.days for ex in d.exercises]
    low, high = expect["exercises_per_day"]
    for day in plan.days:
        assert day.estimated_minutes <= expect["max_minutes"]
        assert low <= len(day.exercises) <= high
    if expect["machines"] == "none":
        assert not any(ex.requires_machine for ex in exercises)
        assert all(contains_term(" ".join([ex.name, *ex.steps]), MACHINE_TERMS) is None for ex in exercises)
    else:
        assert any(ex.requires_machine for ex in exercises)
    if "max_sets" in expect:
        assert max(ex.sets for ex in exercises) <= expect["max_sets"]
    if "max_reps" in expect:
        assert max(ex.reps or 0 for ex in exercises) <= expect["max_reps"]
    if "min_sets" in expect:
        assert min(ex.sets for ex in exercises) >= expect["min_sets"]
