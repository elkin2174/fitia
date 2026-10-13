"""Reintentos, presupuesto y circuit breaker del AIGateway, con tiempo falso (sin red ni BD)."""
import pytest

from app.ai.adapters.fake_text import BrokenJson, Callback, FakeTextAdapter, Fail, Incoherent, Valid
from app.ai.call_log import MemoryCallRecorder
from app.ai.errors import AIFailure
from app.ai.gateway import AIGateway
from app.ai.privacy import WeeklyPlanInput
from app.ai.resilience import CircuitBreaker
from app.ai.use_cases.weekly_plan.use_case import WEEKLY_PLAN
from app.core.clock import FrozenClock
from app.core.config import Settings
from tests.fakes import FakeMonotonic

PLAN_INPUT = WeeklyPlanInput(goal="strength", term_weeks=8, fitness_level="beginner", session_minutes=30,
                             training_days=[1, 3], has_machine_access=False)


class Harness:
    def __init__(self, **overrides: object) -> None:
        self.settings = Settings(_env_file=None, **overrides)
        self.time = FakeMonotonic()
        self.fake = FakeTextAdapter()
        self.recorder = MemoryCallRecorder()
        self.breaker = CircuitBreaker(
            self.settings.AI_BREAKER_FAILURES, self.settings.AI_BREAKER_WINDOW_SECONDS,
            self.settings.AI_BREAKER_OPEN_SECONDS, self.time,
        )
        self.gateway = AIGateway(self.settings, self.fake, self.breaker, self.recorder, FrozenClock(),
                                 time_fn=self.time, sleep=self.time.sleep)

    async def run(self):
        return await self.gateway.run(WEEKLY_PLAN, PLAN_INPUT)

    async def fail(self) -> AIFailure:
        with pytest.raises(AIFailure) as exc:
            await self.run()
        return exc.value

    @property
    def statuses(self) -> list[tuple[str, int]]:
        return [(e.status, e.attempts) for e in self.recorder.entries]


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_exito_al_primer_intento(h: Harness) -> None:
    result = await h.run()

    assert result.attempts == 1 and result.prompt_version == "v1" and result.model == "fake"
    assert h.statuses == [("ok", 1)]


@pytest.mark.parametrize("first", [Fail("timeout"), Fail("server_error"), Fail("rate_limited"), Fail("network"),
                                   BrokenJson(), Incoherent()])
async def test_un_fallo_reintentable_y_luego_exito(h: Harness, first) -> None:
    h.fake.script(first, Valid())

    result = await h.run()

    assert result.attempts == 2 and h.fake.calls == 2
    assert h.statuses == [("ok", 2)]


@pytest.mark.parametrize(
    ("behavior", "code", "status"),
    [
        (lambda: Fail("timeout"), "GENERATION_TIMEOUT", "timeout"),
        (lambda: Fail("server_error"), "AI_UNAVAILABLE", "provider_error"),
        (lambda: Fail("rate_limited"), "AI_UNAVAILABLE", "provider_error"),
        (lambda: BrokenJson(), "AI_INVALID_OUTPUT", "invalid_output"),
        (lambda: Incoherent(), "AI_INVALID_OUTPUT", "invalid_output"),
    ],
)
async def test_dos_fallos_seguidos_dan_el_codigo_final(h: Harness, behavior, code: str, status: str) -> None:
    h.fake.script(behavior(), behavior())

    failure = await h.fail()

    assert (failure.code, failure.call_status, failure.attempts) == (code, status, 2)
    assert h.fake.calls == 2  # máximo 1 reintento
    assert h.statuses == [(status, 2)]


async def test_el_codigo_final_es_el_del_ultimo_intento(h: Harness) -> None:
    h.fake.script(Fail("timeout"), BrokenJson())

    assert (await h.fail()).code == "AI_INVALID_OUTPUT"


async def test_client_error_no_se_reintenta(h: Harness) -> None:
    h.fake.script(Fail("client_error"), Valid())

    failure = await h.fail()

    assert failure.code == "AI_UNAVAILABLE" and failure.attempts == 1 and h.fake.calls == 1


async def test_sin_presupuesto_restante_no_hay_reintento(h: Harness) -> None:
    # El primer intento consume 36 s de los 40: quedan < 5 s → no se reintenta.
    h.fake.script(Callback(lambda: h.time.advance(36), Fail("timeout")), Valid())

    failure = await h.fail()

    assert failure.code == "GENERATION_TIMEOUT" and h.fake.calls == 1


async def test_con_presupuesto_suficiente_si_reintenta(h: Harness) -> None:
    h.fake.script(Callback(lambda: h.time.advance(20), Fail("timeout")), Valid())

    result = await h.run()

    assert result.attempts == 2
    # El segundo intento recibe como timeout lo que queda del presupuesto (40 − 20 − 0,5).
    assert h.fake.requests[1].timeout_seconds == pytest.approx(19.5)


async def test_ia_deshabilitada_no_llama_al_adaptador() -> None:
    h = Harness(AI_ENABLED=False)

    failure = await h.fail()

    assert (failure.code, failure.call_status) == ("AI_UNAVAILABLE", "disabled")
    assert h.fake.calls == 0 and h.statuses == [("disabled", 0)]


async def test_cinco_fallos_de_disponibilidad_abren_el_breaker_y_luego_permite_un_intento(h: Harness) -> None:
    h.fake.script(*[Fail("server_error")] * 5)
    for _ in range(3):  # 2 + 2 + 1 intentos: el 5.º fallo abre el breaker en plena 3.ª ejecución
        await h.fail()
    calls = h.fake.calls
    assert calls == 5 and h.breaker.is_open

    failure = await h.fail()
    assert (failure.code, failure.call_status) == ("AI_UNAVAILABLE", "breaker_open")
    assert h.fake.calls == calls, "con el breaker abierto no se llama al adaptador"

    h.time.advance(30)  # AI_BREAKER_OPEN_SECONDS
    result = await h.run()  # intento de prueba exitoso: se cierra
    assert result.attempts == 1 and not h.breaker.is_open


async def test_intento_de_prueba_fallido_reabre_el_breaker(h: Harness) -> None:
    h.fake.script(*[Fail("server_error")] * 5)
    for _ in range(3):
        await h.fail()
    h.time.advance(30)
    h.fake.script(Fail("server_error"))

    await h.fail()

    assert h.breaker.is_open


async def test_salida_invalida_no_cuenta_para_el_breaker(h: Harness) -> None:
    h.fake.script(*[BrokenJson()] * 10)
    for _ in range(5):
        await h.fail()

    assert not h.breaker.is_open
    assert (await h.run()).attempts == 1


async def test_fallos_fuera_de_la_ventana_no_abren_el_breaker(h: Harness) -> None:
    for _ in range(4):
        h.fake.script(Fail("client_error"))
        await h.fail()
        h.time.advance(20)  # 4 fallos repartidos en más de 60 s

    h.fake.script(Fail("client_error"))
    await h.fail()

    assert not h.breaker.is_open
