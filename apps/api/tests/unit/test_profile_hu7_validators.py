"""Pruebas unitarias de validaciones de HU7 (perfil, mediciones físicas, ranking y campos no editables)."""
import pytest

from app.core.errors import FieldError
from app.modules.profile import options
from app.modules.profile.validators import (
    NON_EDITABLE_FIELDS,
    PROFILE_FIELDS,
    validate_profile_update,
    validation_message,
)


def _codes(errors: list[FieldError]) -> dict[str, str]:
    return {e.field: e.code for e in errors}


def test_validacion_perfil_con_datos_validos() -> None:
    payload = {
        "goal": "endurance",
        "term_weeks": 12,
        "fitness_level": "intermediate",
        "session_minutes": 45,
        "training_days": [1, 2, 4],
        "has_machine_access": True,
        "weight_kg": 70.5,
        "height_cm": 175.0,
        "is_public_ranking": False,
    }
    values, errors = validate_profile_update(payload)
    assert errors == []
    assert values["goal"] == "endurance"
    assert values["weight_kg"] == 70.5
    assert values["height_cm"] == 175.0
    assert values["is_public_ranking"] is False


@pytest.mark.parametrize("weight", [20.0, 70.5, 400.0, 80])
def test_pesos_validos_aceptados(weight: float | int) -> None:
    values, errors = validate_profile_update({"weight_kg": weight})
    assert errors == []
    assert values["weight_kg"] == round(float(weight), 2)


@pytest.mark.parametrize("bad_weight", [19.9, 0, -5, 400.1, 500, "70", True, False, None, []])
def test_pesos_invalidos_rechazados(bad_weight: object) -> None:
    _, errors = validate_profile_update({"weight_kg": bad_weight})
    assert any(e.field == "weight_kg" and e.code in ("INVALID_OPTION", "REQUIRED") for e in errors)


@pytest.mark.parametrize("height", [50.0, 175.5, 270.0, 180])
def test_estaturas_validas_aceptadas(height: float | int) -> None:
    values, errors = validate_profile_update({"height_cm": height})
    assert errors == []
    assert values["height_cm"] == round(float(height), 2)


@pytest.mark.parametrize("bad_height", [49.9, 0, -10, 270.1, 300, "170", True, False, None, []])
def test_estaturas_invalidas_rechazadas(bad_height: object) -> None:
    _, errors = validate_profile_update({"height_cm": bad_height})
    assert any(e.field == "height_cm" and e.code in ("INVALID_OPTION", "REQUIRED") for e in errors)


@pytest.mark.parametrize("ranking_val", [True, False])
def test_visibilidad_ranking_booleano_valido(ranking_val: bool) -> None:
    values, errors = validate_profile_update({"is_public_ranking": ranking_val})
    assert errors == []
    assert values["is_public_ranking"] is ranking_val


@pytest.mark.parametrize("bad_ranking", ["true", "false", 1, 0, None, [], {}])
def test_visibilidad_ranking_no_booleano_rechazado(bad_ranking: object) -> None:
    _, errors = validate_profile_update({"is_public_ranking": bad_ranking})
    assert any(e.field == "is_public_ranking" and e.code in ("INVALID_OPTION", "REQUIRED") for e in errors)


@pytest.mark.parametrize("field", NON_EDITABLE_FIELDS)
def test_campos_no_editables_son_rechazados(field: str) -> None:
    _, errors = validate_profile_update({field: 123})
    assert any(e.field == field and e.code == "NOT_EDITABLE" for e in errors)


def test_campos_desconocidos_con_campo_valido_se_ignoran() -> None:
    values, errors = validate_profile_update({"goal": "strength", "nickname": "Otro", "user_id": "123"})
    assert errors == []
    assert values == {"goal": "strength"}


def test_actualizacion_vacia_no_devuelve_valores() -> None:
    values, errors = validate_profile_update({})
    assert values == {}
    assert errors == []


def test_mensaje_not_editable() -> None:
    msg = validation_message([FieldError("points", "NOT_EDITABLE")])
    assert "no son editables" in msg
