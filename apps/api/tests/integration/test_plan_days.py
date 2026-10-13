"""HU 12 - Calendario semanal y detalle de día (GET /api/v1/plan/days/{date}).

Criterios de Aceptación:
- AC-12-1 / AC-12-2: Día de entrenamiento muestra rutina con ejercicios, series, repeticiones y guía embebida.
- AC-12-3: Día de descanso (o no planificado) se muestra con status 'rest'/'unplanned' y lista vacía de ejercicios.
- AC-12-4: Manejo de errores y límites:
  - Sin plan vigente -> 404 PLAN_NOT_FOUND.
  - Fecha fuera de la semana del plan -> 404 PLAN_DAY_NOT_FOUND.
  - Formato de fecha inválido -> 422.
- Restricción: Solo lectura (PUT, POST, PATCH, DELETE responden 405).
- Seguridad: 401 sin sesión, 403 sin perfil, aislamiento por usuario (NFR-10), Cache-Control: no-store.
- NFR-16: Cero llamadas a la IA.
- NFR-05: Latencia < 2 s.
"""
from datetime import datetime
import time
from zoneinfo import ZoneInfo
import httpx
import pytest

from app.ai.adapters.fake_text import FakeTextAdapter
from app.core.clock import FrozenClock
from app.modules.plan.models import EXERCISE_DISCLAIMER
from tests.conftest import Student, with_session
from tests.fakes import ManualScheduler

BOGOTA = ZoneInfo("America/Bogota")


async def test_ac_12_2_dia_de_entrenamiento_devuelve_detalle_completo_con_ejercicios(
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
    ai_calls = fake_ai.calls

    started = time.perf_counter()
    response = await plan_api.day(token, "2026-10-12")
    elapsed = time.perf_counter() - started

    record_property("plan_day_seconds", round(elapsed, 3))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert fake_ai.calls == ai_calls  # NFR-16: cero llamadas a la IA
    assert elapsed < 2.0  # NFR-05: latencia < 2 s

    data = response.json()
    assert data["date"] == "2026-10-12"
    assert data["weekday"] == 1
    assert data["status"] == "training"
    assert "title" in data
    assert data["estimated_minutes"] is not None and data["estimated_minutes"] > 0

    exercises = data["exercises"]
    assert len(exercises) > 0
    for idx, ex in enumerate(exercises):
        assert ex["position"] == idx + 1
        assert len(ex["name"]) > 0
        assert ex["sets"] > 0
        assert (ex["reps"] is not None) or (ex["work_seconds"] is not None)
        assert ex["rest_seconds"] is not None
        assert "guide" in ex
        assert len(ex["guide"]["steps"]) >= 2
        assert len(ex["guide"]["steps"]) <= 4
        assert ex["guide"]["disclaimer"] == EXERCISE_DISCLAIMER


async def test_ac_12_3_dia_de_descanso_devuelve_status_rest_y_sin_ejercicios(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
) -> None:
    clock.set(datetime(2026, 10, 12, 10, 0, 0, tzinfo=BOGOTA))
    token = student_with_profile.token
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    # Martes 2026-10-13 es descanso
    response = await plan_api.day(token, "2026-10-13")
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-10-13"
    assert data["weekday"] == 2
    assert data["status"] == "rest"
    assert data["exercises"] == []


async def test_ac_12_4_errores_plan_not_found_y_day_not_found(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
) -> None:
    clock.set(datetime(2026, 10, 12, 10, 0, 0, tzinfo=BOGOTA))
    token = student_with_profile.token

    # 1. Sin plan generado -> 404 PLAN_NOT_FOUND
    resp_no_plan = await plan_api.day(token, "2026-10-12")
    assert resp_no_plan.status_code == 404
    assert resp_no_plan.json()["error"]["code"] == "PLAN_NOT_FOUND"

    # Generamos plan para la semana del 12 de oct
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    # 2. Fecha que no pertenece a los días de la semana (ej. fin de semana o semana anterior)
    resp_day_not_found = await plan_api.day(token, "2026-10-18")  # domingo
    assert resp_day_not_found.status_code == 404
    assert resp_day_not_found.json()["error"]["code"] == "PLAN_DAY_NOT_FOUND"

    resp_wrong_week = await plan_api.day(token, "2026-10-05")  # lunes pasado
    assert resp_wrong_week.status_code == 404
    assert resp_wrong_week.json()["error"]["code"] == "PLAN_DAY_NOT_FOUND"


async def test_ac_12_4_formato_de_fecha_invalido_devuelve_422(
    client: httpx.AsyncClient,
    student_with_profile: Student,
) -> None:
    headers = with_session(student_with_profile.token)
    for bad_date in ("no-es-fecha", "2026-13-40", "12-10-2026"):
        resp = await client.get(f"/api/v1/plan/days/{bad_date}", headers=headers)
        assert resp.status_code == 422


async def test_ac_12_restriccion_solo_lectura_y_metodos_no_permitidos(
    client: httpx.AsyncClient,
    student_with_profile: Student,
) -> None:
    headers = with_session(student_with_profile.token)
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        resp = await client.request(method, "/api/v1/plan/days/2026-10-12", headers=headers, json={"exercises": []})
        assert resp.status_code == 405
        assert resp.headers["Cache-Control"] == "no-store"


async def test_ac_12_seguridad_guards_y_aislamiento(
    client: httpx.AsyncClient,
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    student: Student,
    make_student,
    clock: FrozenClock,
) -> None:
    clock.set(datetime(2026, 10, 12, 10, 0, 0, tzinfo=BOGOTA))

    # 1. Sin sesión -> 401
    unauth = await client.get("/api/v1/plan/days/2026-10-12")
    assert unauth.status_code == 401

    # 2. Con sesión pero sin perfil completado -> 403
    without_profile = await make_student("sinperfil@correounivalle.edu.co")
    forbidden = await plan_api.day(without_profile.token, "2026-10-12")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "ONBOARDING_REQUIRED"

    # 3. Aislamiento: estudiante B no ve el plan del estudiante A
    await plan_api.generate(student_with_profile.token)
    await manual_scheduler.run_all()
    # Estudiante A puede ver su día
    assert (await plan_api.day(student_with_profile.token, "2026-10-12")).status_code == 200

    other_student = await make_student("otro@correounivalle.edu.co")
    # Estudiante B sin perfil da 403
    assert (await plan_api.day(other_student.token, "2026-10-12")).status_code == 403
