"""HU 10 - Rutina de hoy (GET /api/v1/plan/today).

Criterios de Aceptación:
- AC-10-1: Camino feliz (día de entrenamiento con ejercicios en orden, series, repeticiones/tiempo, descanso, guide).
- AC-10-2: Día de descanso (entre semana y fin de semana) con próximo día de entrenamiento.
- AC-10-3: Estados none, generating, failed con opción de generar/reintentar.
- AC-10-4: Restricción de solo lectura (PUT, POST, PATCH, DELETE responden 405).
- AC-10-5: Seguridad (401 sin sesión, 403 sin perfil, Cache-Control: no-store).
- NFR-16: Cero llamadas a la IA.
- NFR-05: Latencia < 2 s.
"""
from datetime import datetime
import time
from zoneinfo import ZoneInfo
import httpx
import pytest

from app.ai.adapters.fake_text import FakeTextAdapter, Fail
from app.modules.plan.models import EXERCISE_DISCLAIMER
from app.core.clock import FrozenClock
from tests.conftest import Student, with_session
from tests.fakes import ManualScheduler

BOGOTA = ZoneInfo("America/Bogota")
TODAY_URL = "/api/v1/plan/today"


async def test_ac_10_1_dia_de_entrenamiento_devuelve_ejercicios_en_orden_con_guia(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
    fake_ai: FakeTextAdapter,
    record_property,
) -> None:
    # 2026-10-12 es lunes (día 1), que es uno de los training_days ([5, 1, 3] = lunes, miércoles, viernes)
    clock.set(datetime(2026, 10, 12, 10, 0, 0, tzinfo=BOGOTA))
    token = student_with_profile.token

    await plan_api.generate(token)
    await manual_scheduler.run_all()
    ai_calls = fake_ai.calls

    started = time.perf_counter()
    response = await plan_api.today(token)
    elapsed = time.perf_counter() - started

    record_property("plan_today_seconds", round(elapsed, 3))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert fake_ai.calls == ai_calls  # NFR-16: cero llamadas a la IA
    assert elapsed < 2.0  # NFR-05: latencia < 2 s

    data = response.json()
    assert data["plan_status"] == "ready"
    assert data["date"] == "2026-10-12"
    assert data["is_weekend"] is False
    assert data["day"] is not None
    assert data["day"]["date"] == "2026-10-12"
    assert data["day"]["weekday"] == 1
    assert data["day"]["status"] == "training"
    assert data["next_training_day"] is None

    exercises = data["day"]["exercises"]
    assert len(exercises) > 0
    # Comprobar orden por posición y estructura de prescripción + guía
    for idx, ex in enumerate(exercises):
        assert ex["position"] == idx + 1
        assert "name" in ex and len(ex["name"]) > 0
        assert ex["sets"] > 0
        assert (ex["reps"] is not None) or (ex["work_seconds"] is not None)
        assert ex["rest_seconds"] is not None
        # Guía embebida (AC-13-1 / AC-13-2)
        assert "guide" in ex
        assert len(ex["guide"]["steps"]) >= 2
        assert len(ex["guide"]["steps"]) <= 4
        assert ex["guide"]["disclaimer"] == EXERCISE_DISCLAIMER


async def test_ac_10_2_dia_de_descanso_entre_semana_muestra_proximo_dia(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
) -> None:
    # Generamos el plan cuando estamos en la semana del 12 de oct
    clock.set(datetime(2026, 10, 12, 8, 0, 0, tzinfo=BOGOTA))
    token = student_with_profile.token
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    # Avanzamos al martes 2026-10-13 (descanso). El próximo entrenamiento es miércoles 2026-10-14
    clock.set(datetime(2026, 10, 13, 14, 0, 0, tzinfo=BOGOTA))
    response = await plan_api.today(token)
    assert response.status_code == 200

    data = response.json()
    assert data["plan_status"] == "ready"
    assert data["date"] == "2026-10-13"
    assert data["is_weekend"] is False
    assert data["day"] is not None
    assert data["day"]["date"] == "2026-10-13"
    assert data["day"]["weekday"] == 2
    assert data["day"]["status"] == "rest"
    assert data["day"]["exercises"] == []
    assert data["next_training_day"] is not None
    assert data["next_training_day"]["date"] == "2026-10-14"
    assert data["next_training_day"]["weekday"] == 3
    assert data["next_training_day"]["planned"] is True


async def test_ac_10_2_fin_de_semana_muestra_descanso_y_proximo_dia_semana_siguiente(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    clock: FrozenClock,
) -> None:
    clock.set(datetime(2026, 10, 12, 8, 0, 0, tzinfo=BOGOTA))
    token = student_with_profile.token
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    # Sábado 2026-10-17: fin de semana
    clock.set(datetime(2026, 10, 17, 10, 0, 0, tzinfo=BOGOTA))
    response = await plan_api.today(token)
    assert response.status_code == 200

    data = response.json()
    assert data["plan_status"] == "none"
    assert data["date"] == "2026-10-17"
    assert data["is_weekend"] is True
    assert data["day"] is None
    # Próximo es lunes de la semana siguiente (2026-10-19), pero esa semana aún no tiene plan
    assert data["next_training_day"] is not None
    assert data["next_training_day"]["date"] == "2026-10-19"
    assert data["next_training_day"]["weekday"] == 1
    assert data["next_training_day"]["planned"] is False

    # Ahora si el estudiante genera su plan para la semana entrante:
    await plan_api.generate(token)
    await manual_scheduler.run_all()
    resp_with_plan = await plan_api.today(token)
    data_with_plan = resp_with_plan.json()
    assert data_with_plan["plan_status"] == "ready"
    assert data_with_plan["is_weekend"] is True
    assert data_with_plan["next_training_day"]["planned"] is True
    assert data_with_plan["next_training_day"]["date"] == "2026-10-19"


async def test_ac_10_3_estados_none_generating_y_failed(
    plan_api,
    manual_scheduler: ManualScheduler,
    student_with_profile: Student,
    fake_ai: FakeTextAdapter,
) -> None:
    token = student_with_profile.token

    # 1. Sin plan generado (plan_status = "none")
    resp_none = await plan_api.today(token)
    assert resp_none.status_code == 200
    data_none = resp_none.json()
    assert data_none["plan_status"] == "none"
    assert data_none["day"] is None
    assert data_none["failure"] is None

    # 2. Generando (plan_status = "generating")
    await plan_api.generate(token)
    resp_gen = await plan_api.today(token)
    assert resp_gen.status_code == 200
    data_gen = resp_gen.json()
    assert data_gen["plan_status"] == "generating"
    assert data_gen["day"] is None

    # 3. Falló la generación (plan_status = "failed")
    fake_ai.script(Fail("server_error"), Fail("server_error"))
    await manual_scheduler.run_all()
    resp_fail = await plan_api.today(token)
    assert resp_fail.status_code == 200
    data_fail = resp_fail.json()
    assert data_fail["plan_status"] == "failed"
    assert data_fail["day"] is None
    assert data_fail["failure"]["code"] == "AI_UNAVAILABLE"


async def test_ac_10_4_la_ruta_es_estrictamente_solo_lectura(
    client: httpx.AsyncClient,
    student_with_profile: Student,
) -> None:
    headers = with_session(student_with_profile.token)
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        res = await client.request(method, TODAY_URL, headers=headers, json={"exercises": []})
        assert res.status_code == 405, (method, TODAY_URL)
        assert res.headers["Cache-Control"] == "no-store"


async def test_ac_10_5_seguridad_guards_de_sesion_y_perfil(
    client: httpx.AsyncClient,
    plan_api,
    student: Student,
) -> None:
    # 1. Sin sesión -> 401
    unauth = await client.get(TODAY_URL)
    assert unauth.status_code == 401
    assert unauth.headers["Cache-Control"] == "no-store"

    # 2. Con sesión pero sin perfil completado -> 403
    forbidden = await plan_api.today(student.token)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "ONBOARDING_REQUIRED"
    assert forbidden.headers["Cache-Control"] == "no-store"
