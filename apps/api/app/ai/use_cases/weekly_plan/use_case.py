from pydantic import ValidationError

from app.ai.errors import AIInvalidOutput
from app.ai.privacy import WEEKLY_PLAN_ALLOWED_KEYS, WeeklyPlanInput
from app.ai.use_cases.weekly_plan.rules import ValidatedPlan, validate_weekly_plan
from app.ai.use_cases.weekly_plan.schema import WeeklyPlanOutput
from app.ai.validators import parse_json_output


class WeeklyPlanUseCase:
    """Plan semanal: entrada = 6 datos del diagnóstico; salida = plan validado con las reglas."""

    name = "weekly_plan"
    allowed_keys = WEEKLY_PLAN_ALLOWED_KEYS

    def parse(self, text: str, plan_input: WeeklyPlanInput) -> ValidatedPlan:
        data = parse_json_output(text)
        try:
            output = WeeklyPlanOutput.model_validate(data)
        except ValidationError as exc:
            raise AIInvalidOutput("no_cumple_el_esquema") from exc
        return validate_weekly_plan(output, plan_input)


WEEKLY_PLAN = WeeklyPlanUseCase()
