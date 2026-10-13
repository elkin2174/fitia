"""PromptRegistry: prompts versionados en YAML (prompts/<caso_de_uso>/<versión>.yaml)."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
REQUIRED_KEYS: tuple[str, ...] = (
    "system",
    "template",
    "input_schema",
    "output_schema",
    "model",
    "parameters",
    "validators",
    "failure_policy",
)
MAX_TEMPERATURE = 0.5  # "temperatura baja": salida estable y reproducible
INPUT_PLACEHOLDER = "{{input_json}}"


class PromptRegistryError(Exception):
    pass


@dataclass(frozen=True)
class PromptSpec:
    use_case: str
    version: str
    system: str
    template: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    model: str
    temperature: float
    max_output_tokens: int
    thinking_level: str | None
    validators: tuple[str, ...]
    max_retries: int
    retry_on: frozenset[str]

    def render(self, input_json: str) -> str:
        return self.template.replace(INPUT_PLACEHOLDER, input_json)


class PromptRegistry:
    def __init__(self, base_dir: Path = DEFAULT_PROMPTS_DIR) -> None:
        self._base_dir = base_dir
        self._cache: dict[tuple[str, str], PromptSpec] = {}

    def load(self, use_case: str, version: str) -> PromptSpec:
        key = (use_case, version)
        if key not in self._cache:
            self._cache[key] = self._read(use_case, version)
        return self._cache[key]

    def _read(self, use_case: str, version: str) -> PromptSpec:
        path = self._base_dir / use_case / f"{version}.yaml"
        if not path.is_file():
            raise PromptRegistryError(f"No existe el prompt '{use_case}' versión '{version}' ({path})")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise PromptRegistryError(f"{path}: el YAML debe ser un objeto")
        missing = [k for k in REQUIRED_KEYS if k not in data]
        if missing:
            raise PromptRegistryError(f"{path}: faltan claves {missing}")
        if INPUT_PLACEHOLDER not in data["template"]:
            raise PromptRegistryError(f"{path}: la plantilla debe contener {INPUT_PLACEHOLDER}")

        params = data["parameters"] or {}
        policy = data["failure_policy"] or {}
        try:
            temperature = float(params["temperature"])
            max_tokens = int(params["max_output_tokens"])
            max_retries = int(policy["max_retries"])
            retry_on = frozenset(policy["retry_on"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PromptRegistryError(f"{path}: parámetros o política de fallo inválidos ({exc})") from exc
        if not 0 <= temperature <= MAX_TEMPERATURE:
            raise PromptRegistryError(f"{path}: la temperatura debe estar entre 0 y {MAX_TEMPERATURE}")
        if max_tokens <= 0 or not 0 <= max_retries <= 1:
            raise PromptRegistryError(f"{path}: max_output_tokens > 0 y max_retries entre 0 y 1")

        return PromptSpec(
            use_case=use_case,
            version=version,
            system=str(data["system"]).strip(),
            template=str(data["template"]),
            input_schema=dict(data["input_schema"]),
            output_schema=dict(data["output_schema"]),
            model=str(data["model"]),
            temperature=temperature,
            max_output_tokens=max_tokens,
            thinking_level=params.get("thinking_level"),
            validators=tuple(data["validators"]),
            max_retries=max_retries,
            retry_on=retry_on,
        )


_default_registry = PromptRegistry()


def get_prompt_registry() -> PromptRegistry:
    return _default_registry
