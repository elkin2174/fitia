import pytest

from app.core.errors import FieldError
from app.modules.profile import options
from app.modules.profile.validators import FIELDS, validate_diagnostic, validation_message

VALID = {
    "goal": "strength",
    "term_weeks": 8,
    "fitness_level": "beginner",
    "session_minutes": 30,
    "training_days": [1, 3],
    "has_machine_access": False,
}


def _codes(errors: list[FieldError]) -> dict[str, str]:
    return {e.field: e.code for e in errors}


def test_payload_valido_devuelve_valores_limpios() -> None:
    values, errors = validate_diagnostic(VALID)

    assert errors == []
    assert values == VALID


def test_dias_repetidos_se_deduplican_y_ordenan() -> None:
    values, errors = validate_diagnostic(VALID | {"training_days": [5, 1, 1, 3, 5]})

    assert errors == []
    assert values["training_days"] == [1, 3, 5]


@pytest.mark.parametrize("raw", [None, [], "texto", 42, [VALID]])
def test_cuerpo_que_no_es_objeto_cuenta_como_vacio(raw: object) -> None:
    _, errors = validate_diagnostic(raw)

    assert [e.field for e in errors] == list(FIELDS)
    assert _codes(errors) == {
        "goal": "REQUIRED",
        "term_weeks": "REQUIRED",
        "fitness_level": "REQUIRED",
        "session_minutes": "REQUIRED",
        "has_machine_access": "MACHINE_ACCESS_REQUIRED",
        "training_days": "DAYS_REQUIRED",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("term_weeks", True),  # bool es subclase de int
        ("term_weeks", 4.0),
        ("term_weeks", "4"),
        ("session_minutes", False),
        ("training_days", [True]),
        ("training_days", [1.0]),
        ("training_days", ["1"]),
        ("training_days", (1, 2)),
        ("has_machine_access", 1),
        ("has_machine_access", "true"),
        ("goal", "Strength"),  # sin normalización
        ("goal", " strength"),  # sin trim
    ],
)
def test_tipado_estricto(field: str, value: object) -> None:
    _, errors = validate_diagnostic(VALID | {field: value})

    assert _codes(errors) == {field: "INVALID_OPTION"}


def test_campos_extra_se_ignoran() -> None:
    values, errors = validate_diagnostic(VALID | {"user_id": "x", "weight_kg": 70})

    assert errors == []
    assert set(values) == set(FIELDS)


def test_modo_parcial_solo_valida_lo_presente() -> None:
    values, errors = validate_diagnostic({"goal": "endurance", "term_weeks": None}, partial=True)

    assert values == {"goal": "endurance"}
    assert _codes(errors) == {"term_weeks": "REQUIRED"}
    assert validate_diagnostic({}, partial=True) == ({}, [])


def test_todas_las_opciones_de_options_py_son_validas() -> None:
    for goal in options.GOALS:
        for weeks in options.TERM_WEEKS:
            assert validate_diagnostic(VALID | {"goal": goal, "term_weeks": weeks})[1] == []
    assert validate_diagnostic(VALID | {"training_days": list(options.WEEKDAYS)})[1] == []


def test_mensaje_de_dias_indica_elegir_al_menos_uno() -> None:
    message = validation_message([FieldError("training_days", "DAYS_REQUIRED")])

    assert "al menos un día" in message
    assert "lunes a viernes" in message


def test_mensaje_no_repite_textos() -> None:
    errors = [FieldError("goal", "REQUIRED"), FieldError("term_weeks", "REQUIRED")]

    assert validation_message(errors) == "Responde todas las preguntas del diagnóstico."
