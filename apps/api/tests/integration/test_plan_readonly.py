"""HU 5 - AC-5-9 / NFR-22 (plan inmutable), NFR-16 / NFR-05 (lectura sin IA), NFR-06, NFR-11 y logs."""
import io
import logging
import time

import httpx
import pytest

from app.ai.adapters.fake_text import FakeTextAdapter, Fail, build_valid_plan
from app.core.logging import JsonFormatter
from app.main import app
from tests.conftest import CURRENT_URL, GENERATE_URL, Student, with_session
from tests.fakes import ManualScheduler


async def test_ac_5_9_la_api_no_ofrece_ninguna_operacion_para_modificar_el_plan(
    client: httpx.AsyncClient, plan_api, manual_scheduler, student_with_profile: Student
) -> None:
    paths = {p: sorted(ops) for p, ops in app.openapi()["paths"].items() if p.startswith("/api/v1/plan")}
    assert paths == {GENERATE_URL: ["post"], CURRENT_URL: ["get"]}

    await plan_api.generate(student_with_profile.token)
    await manual_scheduler.run_all()
    headers = with_session(student_with_profile.token)
    for url in (GENERATE_URL, CURRENT_URL):
        for method in ("PUT", "PATCH", "DELETE"):
            response = await client.request(method, url, headers=headers, json={"days": []})
            assert response.status_code == 405, (method, url)
    for url in ("/api/v1/plan", "/api/v1/plan/days/2026-10-12", "/api/v1/plan/exercises/1"):
        for method in ("GET", "PUT", "PATCH", "DELETE", "POST"):
            assert (await client.request(method, url, headers=headers)).status_code in (404, 405)
    assert (await plan_api.current(student_with_profile.token)).json()["status"] == "ready"


async def test_nfr_16_consultar_el_plan_nunca_llama_a_la_ia(
    plan_api, manual_scheduler, student_with_profile: Student, fake_ai: FakeTextAdapter, record_property
) -> None:
    token = student_with_profile.token
    for _ in range(3):
        await plan_api.current(token)  # status none
    assert fake_ai.calls == 0

    fake_ai.script(Fail("server_error"), Fail("server_error"))
    await plan_api.generate(token)
    await manual_scheduler.run_all()
    calls_after_failure = fake_ai.calls
    for _ in range(3):
        assert (await plan_api.current(token)).json()["status"] == "failed"
    assert fake_ai.calls == calls_after_failure  # un fallo no dispara reintentos
    await plan_api.generate(token)
    await manual_scheduler.run_all()
    calls_after_generation = fake_ai.calls

    started = time.perf_counter()
    response = await plan_api.current(token)
    elapsed = time.perf_counter() - started

    assert response.json()["status"] == "ready"
    assert fake_ai.calls == calls_after_generation
    record_property("plan_current_seconds", round(elapsed, 3))
    print(f"\n[NFR-05] GET /plan/current: {elapsed * 1000:.0f} ms")
    assert elapsed < 2.0


async def test_nfr_06_post_generate_responde_rapido(
    plan_api, manual_scheduler, student_with_profile: Student, record_property
) -> None:
    started = time.perf_counter()
    response = await plan_api.generate(student_with_profile.token)
    elapsed = time.perf_counter() - started

    record_property("plan_generate_seconds", round(elapsed, 3))
    print(f"\n[NFR-06] POST /plan/generate (202): {elapsed * 1000:.0f} ms")
    assert response.status_code == 202 and elapsed < 2.0


@pytest.mark.parametrize("method,url", [("POST", GENERATE_URL), ("GET", CURRENT_URL)])
async def test_nfr_11_respuestas_del_plan_llevan_no_store(
    client: httpx.AsyncClient, manual_scheduler, student_with_profile: Student, student, method: str, url: str
) -> None:
    ok = await client.request(method, url, headers=with_session(student_with_profile.token))
    unauthenticated = await client.request(method, url)

    assert ok.status_code in (200, 202)
    assert unauthenticated.status_code == 401
    for response in (ok, unauthenticated):
        assert response.headers["Cache-Control"] == "no-store"


async def test_nfr_11_errores_409_y_403_tambien_llevan_no_store(
    client: httpx.AsyncClient, plan_api, manual_scheduler, student_with_profile: Student, make_student
) -> None:
    await plan_api.generate(student_with_profile.token)
    await manual_scheduler.run_all()
    conflict = await plan_api.generate(student_with_profile.token)
    without_profile = await make_student("sinperfil@correounivalle.edu.co")
    forbidden = await plan_api.current(without_profile.token)

    assert (conflict.status_code, forbidden.status_code) == (409, 403)
    assert conflict.headers["Cache-Control"] == forbidden.headers["Cache-Control"] == "no-store"


async def test_logs_sin_correo_apodo_prompt_respuesta_ni_contenido_del_plan(
    plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student, fake_ai: FakeTextAdapter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("fitia")
    logger.addHandler(handler)
    caplog.set_level(logging.DEBUG)
    try:
        await plan_api.generate(student_with_profile.token)
        await manual_scheduler.run_all()
        await plan_api.current(student_with_profile.token)
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue() + caplog.text
    assert "plan_generation_started" in output and "plan_generated" in output
    request = fake_ai.requests[0]
    plan = build_valid_plan(request.input_data)  # lo mismo que respondió la IA falsa
    plan_texts = [
        text for day in plan["days"] for ex in day["exercises"] for text in (ex["name"], *ex["steps"])
    ] + [day["title"] for day in plan["days"]]
    forbidden = [
        student_with_profile.user.email, "Pantera", request.system[:60], request.prompt[:60], "<<<DATOS",
        '"goal"', "strength", *plan_texts,
    ]
    for secret in forbidden:
        assert secret not in output, f"filtrado en logs: {secret!r}"


async def test_logs_de_una_generacion_fallida(
    plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student, fake_ai: FakeTextAdapter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    fake_ai.script(Fail("timeout"), Fail("timeout"))

    await plan_api.generate(student_with_profile.token)
    await manual_scheduler.run_all()

    failed = [r for r in caplog.records if r.getMessage() == "plan_generation_failed"]
    assert len(failed) == 1
    record = failed[0]
    assert record.failure_code == "GENERATION_TIMEOUT" and record.attempts == 2
    assert student_with_profile.user.email not in caplog.text and "Pantera" not in caplog.text
