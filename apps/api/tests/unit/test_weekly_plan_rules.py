"""Reglas del plan semanal: un plan válido pasa y cada violación se rechaza por separado."""
import copy
import json
from typing import Any

import pytest

from app.ai.adapters.fake_text import build_valid_plan
from app.ai.errors import AIInvalidOutput
from app.ai.privacy import WeeklyPlanInput
from app.ai.use_cases.weekly_plan.rules import day_seconds, exercise_seconds, minutes
from app.ai.use_cases.weekly_plan.use_case import WEEKLY_PLAN

INPUT = WeeklyPlanInput(
    goal="strength", term_weeks=8, fitness_level="intermediate", session_minutes=45,
    training_days=[1, 3, 5], has_machine_access=False,
)
STEP = "Mantén la espalda recta durante todo el movimiento."


def _plan() -> dict[str, Any]:
    return build_valid_plan(INPUT.model_dump())


def _parse(plan: Any, plan_input: WeeklyPlanInput = INPUT):
    return WEEKLY_PLAN.parse(json.dumps(plan, ensure_ascii=False), plan_input)


def _first(plan: dict[str, Any]) -> dict[str, Any]:
    return plan["days"][0]["exercises"][0]


def test_estimador_de_duracion() -> None:
    assert exercise_seconds(3, 10, None, 60) == 3 * 30 + 2 * 60
    assert exercise_seconds(2, None, 40, 30) == 2 * 40 + 30
    assert day_seconds([(3, 10, None, 60), (2, None, 40, 30)]) == 210 + 110 + 30
    assert minutes(61) == 2 and minutes(60) == 1


def test_plan_valido_pasa_y_usa_la_duracion_calculada_por_el_servidor() -> None:
    plan = _plan()
    for day in plan["days"]:
        day["estimated_minutes"] = 1  # la cifra de la IA se ignora

    validated = _parse(plan)

    assert [d.weekday for d in validated.days] == [1, 3, 5]
    for day, raw in zip(validated.days, plan["days"], strict=True):
        shaped = [(e["sets"], e.get("reps"), e.get("work_seconds"), e["rest_seconds"]) for e in raw["exercises"]]
        assert day.estimated_minutes == minutes(day_seconds(shaped)) <= 45


def test_claves_desconocidas_se_ignoran() -> None:
    plan = _plan()
    plan["comentario"] = "hola"
    plan["days"][0]["extra"] = 1
    _first(plan)["user_id"] = "x"

    _parse(plan)


def test_cerca_de_markdown_se_tolera() -> None:
    validated = WEEKLY_PLAN.parse("```json\n" + json.dumps(_plan()) + "\n```", INPUT)

    assert len(validated.days) == 3


def _mutations() -> list[tuple[str, Any]]:
    def mutate(fn):
        plan = _plan()
        fn(plan)
        return plan

    def set_first(key: str, value: Any):
        return lambda p: _first(p).__setitem__(key, value)

    def reps_and_work(p):
        _first(p)["reps"], _first(p)["work_seconds"] = 10, 30

    def neither(p):
        _first(p).pop("reps", None)
        _first(p).pop("work_seconds", None)

    def too_long(p):
        for ex in p["days"][0]["exercises"]:
            ex.update(sets=6, rest_seconds=180)

    def english(p):
        for ex in p["days"][0]["exercises"]:
            ex["steps"] = ["Keep your back straight and hold the position.", "Push the floor with your hands and then return."]

    return [
        ("dia_de_mas", mutate(lambda p: p["days"].append({**copy.deepcopy(p["days"][0]), "weekday": 2}))),
        ("dia_de_menos", mutate(lambda p: p["days"].pop())),
        ("dia_repetido", mutate(lambda p: p["days"].append(copy.deepcopy(p["days"][0])))),
        ("menos_de_3_ejercicios", mutate(lambda p: p["days"][0].__setitem__("exercises", p["days"][0]["exercises"][:2]))),
        ("mas_de_8_ejercicios", mutate(lambda p: p["days"][0]["exercises"].extend(
            {**copy.deepcopy(_first(p)), "name": f"Ejercicio extra {i}", "sets": 1, "reps": 1, "rest_seconds": 15}
            for i in range(9)
        ))),
        ("sesion_excede_minutos", mutate(too_long)),
        ("series_fuera_de_rango", mutate(set_first("sets", 7))),
        ("series_cero", mutate(set_first("sets", 0))),
        ("descanso_fuera_de_rango", mutate(set_first("rest_seconds", 200))),
        ("descanso_bajo", mutate(set_first("rest_seconds", 5))),
        ("reps_y_work_a_la_vez", mutate(reps_and_work)),
        ("ni_reps_ni_work", mutate(neither)),
        ("un_paso", mutate(set_first("steps", [STEP]))),
        ("cinco_pasos", mutate(set_first("steps", [STEP] * 5))),
        ("paso_largo", mutate(set_first("steps", [STEP, "a" * 201]))),
        ("url", mutate(set_first("steps", [STEP, "Mira el video en https://example.com/video"]))),
        ("dominio_sin_esquema", mutate(set_first("steps", [STEP, "Más info en fitia.com"]))),
        ("html", mutate(set_first("steps", [STEP, "Baja <b>despacio</b> sin rebotar."]))),
        ("dieta", mutate(set_first("steps", [STEP, "Acompaña con una dieta alta en proteína."]))),
        ("calorias", mutate(set_first("steps", [STEP, "Quemarás muchas calorías."]))),
        ("nombres_repetidos", mutate(lambda p: p["days"][0]["exercises"][1].__setitem__("name", _first(p)["name"].upper()))),
        ("titulo_vacio", mutate(lambda p: p["days"][0].__setitem__("title", "   "))),
        ("titulo_largo", mutate(lambda p: p["days"][0].__setitem__("title", "T" * 61))),
        ("texto_en_ingles", mutate(english)),
        ("requiere_maquina_sin_acceso", mutate(set_first("requires_machine", True))),
        ("prensa_sin_bandera_ni_acceso", mutate(set_first("name", "Prensa de piernas"))),
        ("maquina_en_un_paso", mutate(set_first("steps", [STEP, "Ajusta el asiento de la máquina."]))),
        ("mancuernas_sin_acceso", mutate(set_first("name", "Curl con mancuernas"))),
        ("bool_como_entero", mutate(set_first("sets", True))),
        ("numero_como_texto", mutate(set_first("rest_seconds", "60"))),
        ("flotante", mutate(set_first("sets", 3.0))),
        ("weekday_como_texto", mutate(lambda p: p["days"][0].__setitem__("weekday", "1"))),
        ("steps_no_lista", mutate(set_first("steps", STEP))),
        ("sin_days", {"plan": []}),
    ]


@pytest.mark.parametrize(("case", "plan"), _mutations(), ids=[c for c, _ in _mutations()])
def test_cada_violacion_se_rechaza(case: str, plan: Any) -> None:
    with pytest.raises(AIInvalidOutput):
        _parse(plan)


@pytest.mark.parametrize("text", ["", "no es json", '{"days": [', "[1, 2]", "null", "```\n{}\n``` extra"])
def test_json_roto_o_no_objeto_es_salida_invalida(text: str) -> None:
    with pytest.raises(AIInvalidOutput):
        WEEKLY_PLAN.parse(text, INPUT)


def test_tope_de_principiante() -> None:
    beginner = INPUT.model_copy(update={"fitness_level": "beginner"})
    plan = build_valid_plan(beginner.model_dump())
    _parse(plan, beginner)

    for field, value in (("sets", 5), ("reps", 21)):
        broken = copy.deepcopy(plan)
        target = next(e for e in broken["days"][0]["exercises"] if field != "reps" or "reps" in e)
        target[field] = value
        with pytest.raises(AIInvalidOutput, match="principiantes"):
            _parse(broken, beginner)


def test_con_acceso_a_maquinas_se_permiten() -> None:
    with_machines = INPUT.model_copy(update={"has_machine_access": True})
    plan = build_valid_plan(with_machines.model_dump())

    validated = _parse(plan, with_machines)

    assert any(ex.requires_machine for day in validated.days for ex in day.exercises)


def test_ac_13_5_sin_steps_rechaza_plan() -> None:
    plan = _plan()
    del _first(plan)["steps"]
    with pytest.raises(AIInvalidOutput):
        _parse(plan)


def test_ac_13_5_steps_vacio_rechaza_plan() -> None:
    plan = _plan()
    _first(plan)["steps"] = []
    with pytest.raises(AIInvalidOutput, match="2 a 4 pasos"):
        _parse(plan)


def test_ac_13_5_un_solo_paso_rechaza_plan() -> None:
    plan = _plan()
    _first(plan)["steps"] = [STEP]
    with pytest.raises(AIInvalidOutput, match="2 a 4 pasos"):
        _parse(plan)


def test_ac_13_5_cinco_pasos_rechaza_plan() -> None:
    plan = _plan()
    _first(plan)["steps"] = [f"Paso {i}: {STEP}" for i in range(1, 6)]
    with pytest.raises(AIInvalidOutput, match="2 a 4 pasos"):
        _parse(plan)


def test_ac_13_5_paso_en_blanco_rechaza_plan() -> None:
    plan = _plan()
    _first(plan)["steps"] = [STEP, "   "]
    with pytest.raises(AIInvalidOutput, match="paso vacío"):
        _parse(plan)
