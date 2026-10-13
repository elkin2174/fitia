"""HU 5 - AC-5-5 / NFR-14: la solicitud a la IA no contiene datos que identifiquen al usuario.

Se verifica en DOS fronteras: (a) lo que recibe el puerto TextGenerator y (b) lo que recibe el
cliente del SDK de Gemini (con el adaptador real y un cliente falso, sin red).
"""
import json
import re
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.ai.adapters.fake_text import FakeTextAdapter, build_valid_plan
from app.ai.adapters.gemini_text import GeminiTextAdapter
from app.ai.call_log import MemoryCallRecorder
from app.ai.gateway import AIGateway, get_ai_gateway
from app.ai.privacy import WEEKLY_PLAN_ALLOWED_KEYS
from app.ai.resilience import CircuitBreaker
from app.core.clock import FrozenClock
from app.core.config import Settings
from app.main import app
from tests.conftest import VALID_DIAGNOSTIC, session_token, with_session
from tests.fakes import FakeMailer, ManualScheduler

NICKNAME = "ZorroPrivado"
EMAIL = "privacidad.zorro@correounivalle.edu.co"
PASSWORD = "ClaveSecreta-Zorro-9"
PROGRAM_CODE, PROGRAM_NAME = "MED", "Medicina y Cirugía"


class RecordingGenaiClient:
    """Cliente falso del SDK: guarda cada llamada y responde un plan válido para la entrada del prompt."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        data = json.loads(kwargs["contents"].split("<<<DATOS", 1)[1].split("DATOS>>>", 1)[0])
        return SimpleNamespace(text=json.dumps(build_valid_plan(data), ensure_ascii=False))


async def _account_with_plan(client: httpx.AsyncClient, mailer: FakeMailer, complete_diagnostic, login) -> dict[str, str]:
    """Cuenta con valores reconocibles, creada por la API, con diagnóstico y plan generado."""
    await client.post("/api/v1/auth/register", json={
        "nickname": NICKNAME, "email": EMAIL, "password": PASSWORD,
        "program_code": PROGRAM_CODE, "accepted_terms": True,
    })
    verify = await client.post("/api/v1/auth/verify-email", json={"token": mailer.last_token()})
    user_id = verify.json()["user"]["id"]
    token = session_token(await login(EMAIL, PASSWORD))
    assert (await complete_diagnostic(token, VALID_DIAGNOSTIC)).status_code == 201
    generate = await client.post("/api/v1/plan/generate", headers=with_session(token))
    return {"user_id": user_id, "plan_id": generate.json()["plan_id"], "token": token}


def _assert_no_personal_data(serialized: str, ids: dict[str, str]) -> None:
    for secret in (NICKNAME, EMAIL, PASSWORD, PROGRAM_NAME, ids["user_id"], ids["plan_id"], ids["token"]):
        assert secret not in serialized, f"dato personal hacia la IA: {secret!r}"
    assert not re.search(rf"\b{PROGRAM_CODE}\b", serialized), "código del programa hacia la IA"
    assert "@correounivalle" not in serialized


async def test_ac_5_5_el_puerto_text_generator_solo_recibe_la_allowlist(
    client: httpx.AsyncClient, mailer: FakeMailer, complete_diagnostic, login,
    manual_scheduler: ManualScheduler, fake_ai: FakeTextAdapter,
) -> None:
    ids = await _account_with_plan(client, mailer, complete_diagnostic, login)
    await manual_scheduler.run_all()

    assert fake_ai.calls == 1
    request = fake_ai.requests[0]
    assert set(request.input_data) == WEEKLY_PLAN_ALLOWED_KEYS
    _assert_no_personal_data(json.dumps(asdict(request), ensure_ascii=False, default=str), ids)


async def test_ac_5_5_el_cliente_de_gemini_solo_recibe_la_allowlist(
    client: httpx.AsyncClient, mailer: FakeMailer, complete_diagnostic, login,
    manual_scheduler: ManualScheduler, settings: Settings, clock: FrozenClock,
) -> None:
    sdk = RecordingGenaiClient()
    gateway = AIGateway(
        settings=settings,
        generator=GeminiTextAdapter(client=sdk),
        breaker=CircuitBreaker(5, 60, 30),
        recorder=MemoryCallRecorder(),
        clock=clock,
    )
    app.dependency_overrides[get_ai_gateway] = lambda: gateway

    ids = await _account_with_plan(client, mailer, complete_diagnostic, login)
    await manual_scheduler.run_all()

    assert len(sdk.calls) == 1
    call = sdk.calls[0]
    serialized = json.dumps(
        {"model": call["model"], "contents": call["contents"], "config": call["config"].model_dump(mode="json")},
        ensure_ascii=False,
    )
    _assert_no_personal_data(serialized, ids)
    sent = json.loads(call["contents"].split("<<<DATOS", 1)[1].split("DATOS>>>", 1)[0])
    assert set(sent) == WEEKLY_PLAN_ALLOWED_KEYS
    assert (await client.get("/api/v1/plan/current", headers=with_session(ids["token"]))).json()["status"] == "ready"
