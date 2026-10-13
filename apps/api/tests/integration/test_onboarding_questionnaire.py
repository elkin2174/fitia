"""HU 4 - GET /onboarding/questionnaire y anti-deriva entre cuestionario, validador y BD."""
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select

from app.core.clock import FrozenClock
from app.modules.profile import options
from app.modules.profile.models import Profile
from tests.conftest import QUESTIONNAIRE_URL, VALID_DIAGNOSTIC, Student, with_session

EXPECTED = [
    ("goal", "single", list(options.GOALS)),
    ("term_weeks", "single", list(options.TERM_WEEKS)),
    ("fitness_level", "single", list(options.FITNESS_LEVELS)),
    ("session_minutes", "single", list(options.SESSION_MINUTES)),
    ("has_machine_access", "single", [True, False]),
    ("training_days", "multi", [1, 2, 3, 4, 5]),
]


async def _questionnaire(client: httpx.AsyncClient, token: str) -> list[dict[str, Any]]:
    response = await client.get(QUESTIONNAIRE_URL, headers=with_session(token))
    assert response.status_code == 200
    return response.json()["questions"]


async def test_cuestionario_tiene_las_6_preguntas_cerradas_en_orden(
    client: httpx.AsyncClient, student: Student
) -> None:
    response = await client.get(QUESTIONNAIRE_URL, headers=with_session(student.token))

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    questions = response.json()["questions"]
    assert [(q["id"], q["type"], [o["code"] for o in q["options"]]) for q in questions] == EXPECTED
    for question in questions:
        assert question["text"].startswith("¿")
        assert question["options"], "ninguna pregunta de texto libre: todas tienen opciones"
        assert all(isinstance(o["label"], str) and o["label"] for o in question["options"])


async def test_codigos_conservan_su_tipo_json(client: httpx.AsyncClient, student: Student) -> None:
    questions = {q["id"]: q for q in await _questionnaire(client, student.token)}

    assert questions["has_machine_access"]["options"] == [{"code": True, "label": "Sí"}, {"code": False, "label": "No"}]
    assert questions["term_weeks"]["options"][0] == {"code": 4, "label": "4 semanas"}
    assert questions["session_minutes"]["options"][0] == {"code": 15, "label": "15 min"}
    assert questions["training_days"]["options"][2] == {"code": 3, "label": "Miércoles"}


async def test_cuestionario_sin_sesion_devuelve_401(client: httpx.AsyncClient) -> None:
    response = await client.get(QUESTIONNAIRE_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_cuestionario_con_sesion_vencida_devuelve_401(
    client: httpx.AsyncClient, student: Student, clock: FrozenClock
) -> None:
    clock.advance(timedelta(days=30, seconds=1))

    assert (await client.get(QUESTIONNAIRE_URL, headers=with_session(student.token))).status_code == 401


async def test_cuestionario_sigue_disponible_con_perfil_completo(
    client: httpx.AsyncClient, student: Student, complete_diagnostic
) -> None:
    assert (await complete_diagnostic(student.token)).status_code == 201

    assert len(await _questionnaire(client, student.token)) == 6


# --- Anti-deriva: el formulario se construye SOLO con lo que devuelve el cuestionario --------


async def test_anti_deriva_envio_armado_desde_el_cuestionario_es_aceptado(
    client: httpx.AsyncClient, student: Student, complete_diagnostic
) -> None:
    questions = await _questionnaire(client, student.token)
    payload = {
        q["id"]: [o["code"] for o in q["options"]] if q["type"] == "multi" else q["options"][0]["code"]
        for q in questions
    }

    response = await complete_diagnostic(student.token, payload)

    assert response.status_code == 201
    assert response.json()["profile"]["training_days"] == [1, 2, 3, 4, 5]


async def test_anti_deriva_cada_codigo_del_cuestionario_es_aceptado_por_el_post(
    client: httpx.AsyncClient, student: Student, make_student, complete_diagnostic, db
) -> None:
    questions = await _questionnaire(client, student.token)
    accepted = 0
    for question in questions:
        for option in question["options"]:
            code = option["code"]
            value = [code] if question["type"] == "multi" else code
            other = await make_student(f"deriva{accepted}@correounivalle.edu.co")

            response = await complete_diagnostic(other.token, VALID_DIAGNOSTIC | {question["id"]: value})

            assert response.status_code == 201, (question["id"], code, response.text)
            stored = await db.scalar(select(Profile).where(Profile.user_id == other.user.id))
            if question["id"] != "training_days":
                assert getattr(stored, question["id"]) == code
            accepted += 1
    assert accepted == sum(len(q["options"]) for q in questions) == 21
