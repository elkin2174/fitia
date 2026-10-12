"""Adaptador Gemini con un cliente falso inyectado (sin red)."""
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai import errors as genai_errors

from app.ai.adapters.gemini_text import GeminiTextAdapter
from app.ai.errors import AIInvalidOutput, AIProviderError
from app.ai.ports import TextRequest

SCHEMA = {"type": "object", "properties": {"days": {"type": "array"}}}


class FakeGenaiClient:
    """Imita client.aio.models.generate_content del SDK."""

    def __init__(self, result: Any = '{"days": []}') -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = result
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._result, BaseException):
            raise self._result
        return SimpleNamespace(text=self._result)


def _request(**overrides: Any) -> TextRequest:
    base = dict(system="Eres un entrenador.", prompt="<<<DATOS {} DATOS>>>", input_data={}, response_schema=SCHEMA,
                temperature=0.2, max_output_tokens=8192, timeout_seconds=12.5, model="gemini-3.8-flash",
                thinking_level="LOW")
    return TextRequest(**(base | overrides))


async def test_envia_system_prompt_esquema_y_parametros() -> None:
    client = FakeGenaiClient()

    text = await GeminiTextAdapter(client=client).generate(_request())

    assert text == '{"days": []}'
    call = client.calls[0]
    config = call["config"]
    assert call["model"] == "gemini-3.8-flash"
    assert call["contents"] == "<<<DATOS {} DATOS>>>"
    assert config.system_instruction == "Eres un entrenador."
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == SCHEMA
    assert config.temperature == 0.2 and config.max_output_tokens == 8192
    assert config.http_options.timeout == 12500  # milisegundos
    assert config.http_options.retry_options is None  # el SDK no reintenta: lo hace el gateway
    assert config.thinking_config.thinking_level.value == "LOW"


def _api_error(cls: type, code: int) -> Exception:
    return cls(code, {"error": {"code": code, "message": "x", "status": "X"}})


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (_api_error(genai_errors.ClientError, 429), "rate_limited"),
        (_api_error(genai_errors.ClientError, 400), "client_error"),
        (_api_error(genai_errors.ClientError, 403), "client_error"),
        (_api_error(genai_errors.ServerError, 500), "server_error"),
        (_api_error(genai_errors.ServerError, 503), "server_error"),
        (httpx.ReadTimeout("lento"), "timeout"),
        (TimeoutError(), "timeout"),
        (httpx.ConnectError("sin red"), "network"),
    ],
)
async def test_mapea_las_excepciones_del_sdk(error: Exception, kind: str) -> None:
    with pytest.raises(AIProviderError) as exc:
        await GeminiTextAdapter(client=FakeGenaiClient(error)).generate(_request())

    assert exc.value.kind == kind


@pytest.mark.parametrize("text", [None, ""])
async def test_respuesta_vacia_es_salida_invalida(text: str | None) -> None:
    with pytest.raises(AIInvalidOutput):
        await GeminiTextAdapter(client=FakeGenaiClient(text)).generate(_request())


async def test_sin_thinking_level_no_envia_thinking_config() -> None:
    client = FakeGenaiClient()

    await GeminiTextAdapter(client=client).generate(_request(thinking_level=None))

    assert client.calls[0]["config"].thinking_config is None
