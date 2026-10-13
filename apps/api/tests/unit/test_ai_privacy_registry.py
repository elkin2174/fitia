from pathlib import Path

import pytest
import yaml

from app.ai.privacy import WEEKLY_PLAN_ALLOWED_KEYS, PrivacyGuard, PrivacyViolation, WeeklyPlanInput
from app.ai.registry import DEFAULT_PROMPTS_DIR, PromptRegistry, PromptRegistryError
from app.ai.use_cases.weekly_plan.schema import DayOut, ExerciseOut, WeeklyPlanOutput

VALID = dict(goal="strength", term_weeks=8, fitness_level="beginner", session_minutes=30,
             training_days=[1, 3], has_machine_access=True)


def test_allowlist_es_exactamente_las_6_respuestas() -> None:
    assert WEEKLY_PLAN_ALLOWED_KEYS == {
        "goal", "term_weeks", "fitness_level", "session_minutes", "training_days", "has_machine_access"
    }


def test_privacy_guard_solo_deja_pasar_la_allowlist() -> None:
    guard = PrivacyGuard(WEEKLY_PLAN_ALLOWED_KEYS)

    assert guard.build(VALID) == VALID
    with pytest.raises(PrivacyViolation, match="nickname"):
        guard.build(VALID | {"nickname": "Pantera"})
    with pytest.raises(PrivacyViolation):
        guard.build({k: v for k, v in VALID.items() if k != "goal"})


def test_weekly_plan_input_rechaza_claves_de_mas() -> None:
    with pytest.raises(ValueError):
        WeeklyPlanInput(**VALID, email="a@correounivalle.edu.co")


def test_registro_carga_el_prompt_v1() -> None:
    spec = PromptRegistry().load("weekly_plan", "v1")

    assert spec.temperature <= 0.5
    assert spec.max_output_tokens >= 4096
    assert spec.max_retries == 1
    assert "client_error" not in spec.retry_on
    assert "<<<DATOS" in spec.render("{}") and "DATOS>>>" in spec.render("{}")


def test_yaml_y_codigo_no_derivan() -> None:
    spec = PromptRegistry().load("weekly_plan", "v1")

    assert set(spec.input_schema["properties"]) == WEEKLY_PLAN_ALLOWED_KEYS
    out = spec.output_schema["properties"]["days"]["items"]
    assert set(out["properties"]) == set(DayOut.model_fields)
    assert set(out["properties"]["exercises"]["items"]["properties"]) == set(ExerciseOut.model_fields)
    assert set(spec.output_schema["properties"]) == set(WeeklyPlanOutput.model_fields)


def test_version_inexistente_falla(tmp_path: Path) -> None:
    with pytest.raises(PromptRegistryError, match="v99"):
        PromptRegistry().load("weekly_plan", "v99")


@pytest.mark.parametrize("missing", ["system", "template", "output_schema", "failure_policy", "parameters"])
def test_claves_faltantes_fallan(tmp_path: Path, missing: str) -> None:
    data = yaml.safe_load((DEFAULT_PROMPTS_DIR / "weekly_plan" / "v1.yaml").read_text(encoding="utf-8"))
    del data[missing]
    (tmp_path / "weekly_plan").mkdir()
    (tmp_path / "weekly_plan" / "v1.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(PromptRegistryError, match=missing):
        PromptRegistry(tmp_path).load("weekly_plan", "v1")


def test_temperatura_alta_falla(tmp_path: Path) -> None:
    data = yaml.safe_load((DEFAULT_PROMPTS_DIR / "weekly_plan" / "v1.yaml").read_text(encoding="utf-8"))
    data["parameters"]["temperature"] = 0.9
    (tmp_path / "weekly_plan").mkdir()
    (tmp_path / "weekly_plan" / "v1.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(PromptRegistryError, match="temperatura"):
        PromptRegistry(tmp_path).load("weekly_plan", "v1")
