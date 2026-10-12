"""Validación cerrada del diagnóstico (NFR-13): tipos estrictos y valores solo de options.py.

Acumula TODOS los errores por campo. Con `partial=True` solo valida los campos presentes;
lo reutilizará la HU 6 (PATCH /profile).
"""
from typing import Any

from app.core.errors import FieldError
from app.modules.profile import options

# Orden de las preguntas: también es el orden de los errores devueltos.
FIELDS: tuple[str, ...] = (
    "goal",
    "term_weeks",
    "fitness_level",
    "session_minutes",
    "has_machine_access",
    "training_days",
)

_REQUIRED_CODE = {"has_machine_access": "MACHINE_ACCESS_REQUIRED", "training_days": "DAYS_REQUIRED"}

_STR_OPTIONS: dict[str, tuple[str, ...]] = {"goal": options.GOALS, "fitness_level": options.FITNESS_LEVELS}
_INT_OPTIONS: dict[str, tuple[int, ...]] = {
    "term_weeks": options.TERM_WEEKS,
    "session_minutes": options.SESSION_MINUTES,
}

_MESSAGES = {
    "REQUIRED": "Responde todas las preguntas del diagnóstico.",
    "MACHINE_ACCESS_REQUIRED": "Indica si tienes acceso a máquinas.",
    "DAYS_REQUIRED": "Elige al menos un día para entrenar, de lunes a viernes.",
    "INVALID_OPTION": "Hay respuestas que no corresponden a las opciones disponibles.",
    "EMPTY_UPDATE": "Debes incluir al menos un campo del diagnóstico para actualizar.",
}


def _is_int(value: Any) -> bool:
    # bool es subclase de int en Python: `true` no debe pasar como 1.
    return type(value) is int


def _check(field: str, value: Any) -> tuple[Any, str | None]:
    """Devuelve (valor_limpio, None) o (None, código_de_error)."""
    if field in _STR_OPTIONS:
        ok = type(value) is str and value in _STR_OPTIONS[field]
        return (value, None) if ok else (None, "INVALID_OPTION")
    if field in _INT_OPTIONS:
        ok = _is_int(value) and value in _INT_OPTIONS[field]
        return (value, None) if ok else (None, "INVALID_OPTION")
    if field == "has_machine_access":
        return (value, None) if type(value) is bool else (None, "INVALID_OPTION")
    # training_days
    if type(value) is not list:
        return None, "INVALID_OPTION"
    if not value:
        return None, "DAYS_REQUIRED"
    if not all(_is_int(day) and day in options.WEEKDAYS for day in value):
        return None, "INVALID_OPTION"
    return sorted(set(value)), None  # repetidos se deduplican; se guardan ordenados


def validate_diagnostic(raw: Any, *, partial: bool = False) -> tuple[dict[str, Any], list[FieldError]]:
    """Valida el cuerpo crudo. Cualquier cosa que no sea un objeto JSON cuenta como `{}`.
    Los campos que no son del diagnóstico se ignoran."""
    data: dict[str, Any] = raw if isinstance(raw, dict) else {}
    values: dict[str, Any] = {}
    errors: list[FieldError] = []
    for field in FIELDS:
        if field not in data and partial:
            continue
        value = data.get(field)
        if value is None:
            errors.append(FieldError(field, _REQUIRED_CODE.get(field, "REQUIRED")))
            continue
        cleaned, error = _check(field, value)
        if error:
            errors.append(FieldError(field, error))
        else:
            values[field] = cleaned
    return values, errors


def validation_message(errors: list[FieldError]) -> str:
    """Mensaje principal: un texto por cada tipo de error, sin repetir (mismo patrón que el registro)."""
    codes = dict.fromkeys(e.code for e in errors)
    return " ".join(_MESSAGES.get(code, "Hay respuestas que no corresponden a las opciones disponibles.") for code in codes)
