"""HU 13 - Explicación de ejercicios (GET /api/v1/plan/exercises/{exercise_id}/guide).

Criterios de Aceptación:
- AC-13-1: Consulta de guía de técnica de un ejercicio propio responde 200.
- AC-13-2: Contenido: entre 2 y 4 pasos breves y el aviso orientativo oficial.
- AC-13-3: Sin llamadas a la IA (NFR-16) y latencia < 2 s (AC-13-4 / NFR-05).
- AC-13-5 / Seguridad:
  - Ejercicio inexistente -> 404 EXERCISE_NOT_FOUND.
  - Ejercicio de otro usuario -> 404 EXERCISE_NOT_FOUND (Decisión 12: no revela existencia con 403).
  - UUID inválido -> 422.
  - Métodos mutantes (POST, PUT, PATCH, DELETE) -> 405 METHOD_NOT_ALLOWED.
  - 401 sin sesión, 403 sin diagnóstico completo, Cache-Control: no-store.
"""
from datetime import datetime
import time
import uuid
from zoneinfo import ZoneInfo
import httpx
import pytest

from app.ai.adapters.fake_text import FakeTextAdapter
from app.core.clock import FrozenClock
from app.modules.plan.models import EXERCISE_DISCLAIMER
from tests.conftest import Student, with_session
from tests.fakes import ManualScheduler

BOGOTA = ZoneInfo("America/Bogota")


async def test_ac_13_1_y_13_2_guia_de_ejercicio_propio_devuelve_pasos_y_disclaimer(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
    fake_ai: FakeTextAdapter,
    record_property,
) -> None:
    clock.set(datetime(2026, 10, 12, 10, 0, 0, tzinfo=BOGOTA))
    token = student_with_profile.token
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    # Obtenemos el día de hoy para conocer el id de un ejercicio
    today_res = await plan_api.today(token)
    assert today_res.status_code == 200
    exercises = today_res.json()["day"]["exercises"]
    assert len(exercises) > 0
    target_exercise = exercises[0]
    exercise_id = target_exercise["id"]

    ai_calls = fake_ai.calls
    started = time.perf_counter()
    response = await plan_api.guide(token, exercise_id)
    elapsed = time.perf_counter() - started

    record_property("plan_guide_seconds", round(elapsed, 3))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert fake_ai.calls == ai_calls  # AC-13-4 / NFR-16: Cero llamadas a la IA
    assert elapsed < 2.0  # AC-13-4 / NFR-05: Carga en <= 2 s

    data = response.json()
    assert data["exercise_id"] == exercise_id
    assert data["name"] == target_exercise["name"]
    assert len(data["steps"]) >= 2
    assert len(data["steps"]) <= 4
    for step in data["steps"]:
        assert isinstance(step, str) and len(step.strip()) > 0
    assert data["disclaimer"] == EXERCISE_DISCLAIMER


async def test_ac_13_5_ejercicio_inexistente_devuelve_404(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
) -> None:
    clock.set(datetime(2026, 10, 12, 10, 0, 0, tzinfo=BOGOTA))
    token = student_with_profile.token
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    random_id = uuid.uuid4()
    response = await plan_api.guide(token, random_id)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXERCISE_NOT_FOUND"


async def test_ac_13_5_aislamiento_ejercicio_de_otro_usuario_devuelve_404(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    make_student,
    complete_diagnostic,
    clock: FrozenClock,
) -> None:
    clock.set(datetime(2026, 10, 12, 10, 0, 0, tzinfo=BOGOTA))
    # Estudiante A genera su plan
    await plan_api.generate(student_with_profile.token)
    await manual_scheduler.run_all()

    today_res = await plan_api.today(student_with_profile.token)
    exercise_id_a = today_res.json()["day"]["exercises"][0]["id"]

    # Estudiante B con perfil completo y su propio plan
    student_b = await make_student("estudiante.b@correounivalle.edu.co")
    await complete_diagnostic(student_b.token)
    await plan_api.generate(student_b.token)
    await manual_scheduler.run_all()

    # Estudiante B intenta acceder al ejercicio de Estudiante A
    # Decisión 12: responde 404 (no 403) para no revelar existencia
    response = await plan_api.guide(student_b.token, exercise_id_a)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXERCISE_NOT_FOUND"


async def test_ac_13_uuid_invalido_devuelve_422(
    client: httpx.AsyncClient,
    student_with_profile: Student,
) -> None:
    headers = with_session(student_with_profile.token)
    res = await client.get("/api/v1/plan/exercises/no-es-uuid/guide", headers=headers)
    assert res.status_code == 422


async def test_ac_13_restriccion_solo_lectura_y_metodos_no_permitidos(
    client: httpx.AsyncClient,
    student_with_profile: Student,
) -> None:
    headers = with_session(student_with_profile.token)
    dummy_id = uuid.uuid4()
    url = f"/api/v1/plan/exercises/{dummy_id}/guide"
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        res = await client.request(method, url, headers=headers, json={"steps": []})
        assert res.status_code == 405
        assert res.headers["Cache-Control"] == "no-store"


async def test_ac_13_seguridad_guards_de_sesion_y_perfil(
    client: httpx.AsyncClient,
    plan_api,
    make_student,
) -> None:
    dummy_id = uuid.uuid4()
    # 1. Sin sesión -> 401
    unauth = await client.get(f"/api/v1/plan/exercises/{dummy_id}/guide")
    assert unauth.status_code == 401

    # 2. Con sesión pero sin perfil completado -> 403
    without_profile = await make_student("sinperfil.guide@correounivalle.edu.co")
    forbidden = await plan_api.guide(without_profile.token, dummy_id)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "ONBOARDING_REQUIRED"
