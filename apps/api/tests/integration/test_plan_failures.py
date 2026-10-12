"""HU 5 - Fallos y degradación (AC-5-6, NFR-15) y generación no bloqueante (AC-5-8, NFR-06)."""
import asyncio
import time
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.ai.adapters.fake_text import BrokenJson, FakeTextAdapter, Fail, Incoherent, Wait
from app.ai.gateway import AIGateway
from app.core.clock import FrozenClock
from app.core.config import Settings
from app.main import app
from app.modules.plan.models import PlanDay, PlanExercise, WeeklyPlan
from app.modules.plan.repository import PlanRepository
from tests.conftest import CSRF_HEADERS, GENERATE_URL, Student, with_session
from tests.fakes import ManualScheduler


async def _plan_rows(db: AsyncSession) -> tuple[int, int]:
    days = await db.scalar(select(func.count()).select_from(PlanDay)) or 0
    exercises = await db.scalar(select(func.count()).select_from(PlanExercise)) or 0
    return days, exercises


# --- AC-5-6: fallos de la IA ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("script", "code"),
    [
        (lambda: [Fail("timeout"), Fail("timeout")], "GENERATION_TIMEOUT"),
        (lambda: [Fail("server_error"), Fail("server_error")], "AI_UNAVAILABLE"),
        (lambda: [Fail("rate_limited"), Fail("rate_limited")], "AI_UNAVAILABLE"),
        (lambda: [Fail("client_error")], "AI_UNAVAILABLE"),
        (lambda: [BrokenJson(), BrokenJson()], "AI_INVALID_OUTPUT"),
        (lambda: [Incoherent(), Incoherent()], "AI_INVALID_OUTPUT"),
    ],
    ids=["timeout", "5xx", "429", "4xx", "json-roto", "incoherente"],
)
async def test_ac_5_6_si_la_ia_falla_no_se_guarda_nada_y_se_puede_reintentar(
    plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student, db: AsyncSession,
    fake_ai: FakeTextAdapter, script, code: str,
) -> None:
    token = student_with_profile.token
    fake_ai.script(*script())
    await plan_api.generate(token)
    await manual_scheduler.run_all()

    body = (await plan_api.current(token)).json()
    assert body["status"] == "failed"
    assert body["failure"] == {"code": code}
    assert await _plan_rows(db) == (0, 0)
    assert await db.scalar(text("SELECT status FROM ai_call_logs")) != "ok"

    retry = await plan_api.generate(token)  # reintento: genera un plan nuevo
    await manual_scheduler.run_all()

    assert retry.status_code == 202
    after = (await plan_api.current(token)).json()
    assert after["status"] == "ready" and after["failure"] is None
    assert (await db.scalars(select(WeeklyPlan.status))).all() == ["ready"]


async def test_ac_5_6_ia_deshabilitada_falla_sin_llamar(
    plan_api, manual_scheduler, student_with_profile: Student, settings: Settings, fake_ai: FakeTextAdapter, db
) -> None:
    settings.AI_ENABLED = False
    await plan_api.generate(student_with_profile.token)
    await manual_scheduler.run_all()

    assert fake_ai.calls == 0
    assert (await plan_api.current(student_with_profile.token)).json()["failure"] == {"code": "AI_UNAVAILABLE"}
    assert await db.scalar(text("SELECT status FROM ai_call_logs")) == "disabled"


async def test_ac_5_6_breaker_abierto_falla_sin_llamar(
    plan_api, manual_scheduler, student_with_profile: Student, ai_gateway: AIGateway, fake_ai: FakeTextAdapter, db
) -> None:
    for _ in range(5):
        ai_gateway.breaker.record_failure()

    await plan_api.generate(student_with_profile.token)
    await manual_scheduler.run_all()

    assert fake_ai.calls == 0
    assert (await plan_api.current(student_with_profile.token)).json()["failure"] == {"code": "AI_UNAVAILABLE"}
    assert await db.scalar(text("SELECT status FROM ai_call_logs")) == "breaker_open"


async def test_ac_5_6_error_al_guardar_el_cuarto_ejercicio_revierte_todo(
    plan_api, manual_scheduler, student_with_profile: Student, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = PlanRepository.add_exercise
    calls = {"n": 0}

    async def _fails_on_fourth(self: PlanRepository, exercise: PlanExercise) -> None:
        calls["n"] += 1
        if calls["n"] == 4:
            raise RuntimeError("fallo simulado de BD")
        await original(self, exercise)

    monkeypatch.setattr(PlanRepository, "add_exercise", _fails_on_fourth)
    await plan_api.generate(student_with_profile.token)
    await manual_scheduler.run_all()

    assert calls["n"] == 4
    assert await _plan_rows(db) == (0, 0)
    body = (await plan_api.current(student_with_profile.token)).json()
    assert body["status"] == "failed" and body["failure"] == {"code": "AI_UNAVAILABLE"}
    assert (await db.scalars(select(WeeklyPlan.status))).all() == ["failed"]


async def test_ac_5_6_una_regeneracion_fallida_no_reemplaza_el_plan_vigente(
    plan_api, manual_scheduler, student_with_profile: Student, db: AsyncSession, fake_ai: FakeTextAdapter
) -> None:
    token = student_with_profile.token
    await plan_api.generate(token)
    await manual_scheduler.run_all()
    days_before = await _plan_rows(db)
    await db.execute(text("UPDATE profiles SET goal = 'endurance'"))
    await db.commit()
    fake_ai.script(Fail("timeout"), Fail("timeout"))

    await plan_api.generate(token)
    await manual_scheduler.run_all()

    body = (await plan_api.current(token)).json()
    assert body["status"] == "ready" and body["generation_number"] == 1
    assert body["failure"] == {"code": "GENERATION_TIMEOUT"}
    assert body["outdated"] is True and body["can_regenerate"] is True
    assert await _plan_rows(db) == days_before


# --- AC-5-8: generación en curso sin bloquear ------------------------------------------


async def test_ac_5_8_mientras_se_genera_el_usuario_no_queda_bloqueado(
    client: httpx.AsyncClient, plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student
) -> None:
    token = student_with_profile.token
    await plan_api.generate(token)

    assert (await plan_api.current(token)).json()["status"] == "generating"
    assert (await client.get("/api/v1/me", headers=with_session(token))).status_code == 200
    assert (await client.post("/api/v1/auth/logout", headers=with_session(token))).status_code == 204
    await manual_scheduler.run_all()  # la tarea termina igual aunque la sesión ya no exista


class _ResponseSentProbe:
    """Middleware ASGI de prueba (técnica de la HU 1): marca cuándo se envió el cuerpo final."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.sent_at: float | None = None

    async def __call__(self, scope, receive, send) -> None:
        async def _send(message) -> None:
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                self.sent_at = time.perf_counter()

        await self.inner(scope, receive, _send)


async def test_ac_5_8_la_llamada_a_la_ia_ocurre_despues_de_responder_aunque_sea_lenta(
    client: httpx.AsyncClient, student_with_profile: Student, fake_ai: FakeTextAdapter, db: AsyncSession,
    record_property,
) -> None:
    # Sin manual_scheduler: BackgroundTasks real. La IA tarda 1,5 s en responder.
    release = asyncio.Event()
    entered = asyncio.Event()
    fake_ai.script(Wait(release, entered))
    probe = _ResponseSentProbe(app)
    observed: dict[str, float | None] = {}

    async def _watch() -> None:
        await entered.wait()
        observed["response_sent_at_ai_call"] = probe.sent_at
        asyncio.get_running_loop().call_later(1.5, release.set)

    watcher = asyncio.create_task(_watch())
    started = time.perf_counter()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=probe), base_url="http://test",
                                 headers={**CSRF_HEADERS, **with_session(student_with_profile.token)}) as raw:
        response = await raw.post(GENERATE_URL)
    await asyncio.wait_for(watcher, timeout=5)

    assert response.status_code == 202
    assert observed["response_sent_at_ai_call"] is not None, "la IA se llamó antes de enviar la respuesta"
    elapsed = probe.sent_at - started
    record_property("plan_generate_response_seconds", round(elapsed, 3))
    print(f"\n[NFR-06] POST /plan/generate respondió en {elapsed * 1000:.0f} ms con la IA tardando 1,5 s")
    assert elapsed < 2.0
    assert (await db.scalars(select(WeeklyPlan.status))).all() == ["ready"]


async def test_ac_5_8_durante_la_espera_a_la_ia_no_hay_transacciones_abiertas(
    plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student, fake_ai: FakeTextAdapter,
    engine: AsyncEngine,
) -> None:
    release, entered = asyncio.Event(), asyncio.Event()
    fake_ai.script(Wait(release, entered))
    await plan_api.generate(student_with_profile.token)

    job = asyncio.create_task(manual_scheduler.run_all())
    await entered.wait()  # la tarea está esperando a la IA
    async with engine.connect() as conn:
        idle_in_tx = await conn.scalar(
            text(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                "AND state LIKE 'idle in transaction%' AND pid <> pg_backend_pid()"
            )
        )
        await conn.rollback()
    release.set()
    await job

    assert idle_in_tx == 0
    assert (await plan_api.current(student_with_profile.token)).json()["status"] == "ready"


# --- STALE: generación huérfana (reinicio de la instancia) --------------------------------


async def test_stale_una_generacion_huerfana_pasa_a_failed_y_se_puede_reintentar(
    plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student, clock: FrozenClock,
    db: AsyncSession,
) -> None:
    token = student_with_profile.token
    orphan_id = (await plan_api.generate(token)).json()["plan_id"]  # su tarea "se pierde"

    clock.advance(timedelta(seconds=89))
    assert (await plan_api.current(token)).json()["status"] == "generating"

    clock.advance(timedelta(seconds=2))  # 91 s
    stale = (await plan_api.current(token)).json()
    assert stale["status"] == "failed" and stale["failure"] == {"code": "STALE"}

    retry = await plan_api.generate(token)
    assert retry.status_code == 202 and retry.json()["plan_id"] != orphan_id

    await manual_scheduler.run_next()  # la tarea original termina tarde: no escribe nada
    assert (await db.scalars(select(WeeklyPlan.status))).all() == ["generating"]
    assert await _plan_rows(db) == (0, 0)

    await manual_scheduler.run_next()
    body = (await plan_api.current(token)).json()
    assert body["status"] == "ready" and body["failure"] is None


async def test_stale_tambien_se_detecta_al_generar(
    plan_api, manual_scheduler: ManualScheduler, student_with_profile: Student, clock: FrozenClock, db
) -> None:
    token = student_with_profile.token
    first = (await plan_api.generate(token)).json()["plan_id"]
    clock.advance(timedelta(seconds=91))

    second = (await plan_api.generate(token)).json()["plan_id"]

    assert second != first
    statuses = dict((str(i), s) for i, s in (await db.execute(select(WeeklyPlan.id, WeeklyPlan.status))).all())
    assert statuses == {second: "generating"}  # la fallida STALE se borró al iniciar la nueva
