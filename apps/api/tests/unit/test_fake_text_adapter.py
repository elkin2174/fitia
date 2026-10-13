import asyncio
import itertools
import json

import pytest

from app.ai.adapters.fake_text import (
    BrokenJson,
    FakeTextAdapter,
    Fail,
    Incoherent,
    Wait,
    build_valid_plan,
)
from app.ai.errors import AIInvalidOutput, AIProviderError
from app.ai.ports import TextRequest
from app.ai.privacy import WeeklyPlanInput
from app.ai.use_cases.weekly_plan.rules import MACHINE_TERMS, contains_term
from app.ai.use_cases.weekly_plan.use_case import WEEKLY_PLAN

GOALS = ["general_health", "strength", "endurance", "weight_loss"]
LEVELS = ["beginner", "intermediate", "advanced"]
MINUTES = [15, 30, 45, 60]
DAY_SETS = [[1], [5], [2, 4], [1, 3, 5], [1, 2, 3, 4, 5]]


@pytest.mark.parametrize("has_machine_access", [True, False])
def test_toda_combinacion_produce_un_plan_que_pasa_las_reglas(has_machine_access: bool) -> None:
    checked = 0
    for goal, level, mins, days in itertools.product(GOALS, LEVELS, MINUTES, DAY_SETS):
        plan_input = WeeklyPlanInput(
            goal=goal, term_weeks=8, fitness_level=level, session_minutes=mins,
            training_days=days, has_machine_access=has_machine_access,
        )
        validated = WEEKLY_PLAN.parse(json.dumps(build_valid_plan(plan_input.model_dump())), plan_input)
        assert [d.weekday for d in validated.days] == days
        assert all(d.estimated_minutes <= mins for d in validated.days)
        if not has_machine_access:
            for day in validated.days:
                for ex in day.exercises:
                    assert not ex.requires_machine
                    assert contains_term(" ".join([ex.name, *ex.steps]), MACHINE_TERMS) is None
        checked += 1
    assert checked == 4 * 3 * 4 * 5


def test_volumen_se_adapta_al_nivel() -> None:
    def max_sets(level: str) -> int:
        plan = build_valid_plan(dict(goal="strength", term_weeks=8, fitness_level=level, session_minutes=60,
                                     training_days=[1], has_machine_access=False))
        return max(e["sets"] for e in plan["days"][0]["exercises"])

    assert max_sets("beginner") < max_sets("intermediate") < max_sets("advanced")


def _request() -> TextRequest:
    data = dict(goal="strength", term_weeks=8, fitness_level="beginner", session_minutes=30,
                training_days=[1, 3], has_machine_access=False)
    return TextRequest(system="s", prompt="p", input_data=data, response_schema=None,
                       temperature=0.2, max_output_tokens=100, timeout_seconds=5)


async def test_modo_guion_consume_comportamientos_en_orden() -> None:
    fake = FakeTextAdapter()
    release = asyncio.Event()
    fake.script(BrokenJson(), Incoherent(), Fail("server_error"), Wait(release))
    request = _request()
    plan_input = WeeklyPlanInput(**request.input_data)

    with pytest.raises(AIInvalidOutput):
        WEEKLY_PLAN.parse(await fake.generate(request), plan_input)
    with pytest.raises(AIInvalidOutput, match="repetidos"):
        WEEKLY_PLAN.parse(await fake.generate(request), plan_input)
    with pytest.raises(AIProviderError) as exc:
        await fake.generate(request)
    assert exc.value.kind == "server_error"

    waiting = asyncio.create_task(fake.generate(request))
    await asyncio.sleep(0)
    assert not waiting.done()
    release.set()
    WEEKLY_PLAN.parse(await waiting, plan_input)
    # Sin guion: respuesta válida por defecto.
    WEEKLY_PLAN.parse(await fake.generate(request), plan_input)
    assert fake.calls == 5
