"""PrivacyGuard (NFR-14 / AC-5-5): la IA solo recibe una allowlist CERRADA de datos."""
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr


class PrivacyViolation(Exception):
    pass


class WeeklyPlanInput(BaseModel):
    """Entrada del plan semanal: los 6 datos del diagnóstico, nada más. Vive en `ai` para no depender de `profile`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    goal: StrictStr
    term_weeks: StrictInt
    fitness_level: StrictStr
    session_minutes: StrictInt
    training_days: list[StrictInt]
    has_machine_access: StrictBool


WEEKLY_PLAN_ALLOWED_KEYS: frozenset[str] = frozenset(WeeklyPlanInput.model_fields)


class PrivacyGuard:
    def __init__(self, allowed_keys: frozenset[str]) -> None:
        self._allowed = allowed_keys

    def build(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Devuelve exactamente las claves permitidas; cualquier clave de más o de menos es un error."""
        keys = set(data)
        extra, missing = keys - self._allowed, self._allowed - keys
        if extra:
            raise PrivacyViolation(f"claves no permitidas hacia la IA: {sorted(extra)}")
        if missing:
            raise PrivacyViolation(f"faltan claves de la allowlist: {sorted(missing)}")
        return {key: data[key] for key in sorted(self._allowed)}
