"""Adaptador delgado sobre el SDK oficial `google-genai` (verificado con la versión 2.29.0).

- client.aio.models.generate_content(model=..., contents=..., config=GenerateContentConfig(...))
- Salida estructurada: response_mime_type="application/json" + response_json_schema.
- HttpOptions.timeout está en milisegundos. Sin retry_options el SDK NO reintenta (lo hace el gateway).
- Errores: errors.ClientError (4xx, incluido 429), errors.ServerError (5xx), httpx para timeout/red.
"""
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.ai.errors import AIInvalidOutput, AIProviderError
from app.ai.ports import TextGenerator, TextRequest


def _from_status(code: int | None) -> AIProviderError:
    if code == 429:
        return AIProviderError("rate_limited", "429")
    if code is not None and code >= 500:
        return AIProviderError("server_error", str(code))
    return AIProviderError("client_error", str(code))


class GeminiTextAdapter(TextGenerator):
    model_name = ""  # se registra el modelo solicitado

    def __init__(self, api_key: str = "", client: Any = None) -> None:
        # `client` permite inyectar un cliente falso en pruebas (sin red).
        self._client = client if client is not None else genai.Client(api_key=api_key)

    def build_config(self, request: TextRequest) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=request.system,
            response_mime_type="application/json",
            response_json_schema=dict(request.response_schema) if request.response_schema else None,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            thinking_config=(
                types.ThinkingConfig(thinking_level=request.thinking_level) if request.thinking_level else None
            ),
            http_options=types.HttpOptions(timeout=int(request.timeout_seconds * 1000)),
        )

    async def generate(self, request: TextRequest) -> str:
        try:
            response = await self._client.aio.models.generate_content(
                model=request.model, contents=request.prompt, config=self.build_config(request)
            )
        except genai_errors.APIError as exc:  # ClientError (4xx) y ServerError (5xx) heredan de APIError
            raise _from_status(getattr(exc, "code", None)) from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise AIProviderError("timeout") from exc
        except (httpx.TransportError, OSError) as exc:
            raise AIProviderError("network", type(exc).__name__) from exc

        text = getattr(response, "text", None)
        if not text:  # bloqueo de seguridad, corte por tokens, etc.
            raise AIInvalidOutput("respuesta_vacia")
        return text
