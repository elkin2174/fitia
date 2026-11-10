"""Adaptador de síntesis de voz (TTS) sobre el SDK oficial `google-genai` (v2.29.0).

- client.aio.models.generate_content(model=..., contents=..., config=GenerateContentConfig(...))
- Modalidad: response_modalities=["AUDIO"] + SpeechConfig con PrebuiltVoiceConfig.
- HttpOptions.timeout en milisegundos.
- Salida: bytes WAV ya empaquetados (detecta RIFF o empaqueta PCM crudo con módulo `wave`).
- Errores: APIError (ClientError/ServerError), TimeoutError, httpx para red.
"""
import io
from typing import Any
import wave

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.ai.adapters.gemini_text import _from_status
from app.ai.errors import AIInvalidOutput, AIProviderError
from app.ai.ports import SpeechRequest, SpeechSynthesizer


def pack_pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Empaqueta muestras PCM crudas en un contenedor WAV estándar RIFF."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


class GeminiSpeechAdapter(SpeechSynthesizer):
    model_name = ""

    def __init__(self, api_key: str = "", client: Any = None) -> None:
        self._client = client if client is not None else genai.Client(api_key=api_key)

    def build_config(self, request: SpeechRequest) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=request.voice)
                )
            ),
            http_options=types.HttpOptions(timeout=int(request.timeout_seconds * 1000)),
        )

    async def synthesize(self, request: SpeechRequest) -> bytes:
        try:
            response = await self._client.aio.models.generate_content(
                model=request.model,
                contents=request.text,
                config=self.build_config(request),
            )
        except genai_errors.APIError as exc:
            raise _from_status(getattr(exc, "code", None)) from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise AIProviderError("timeout") from exc
        except (httpx.TransportError, OSError) as exc:
            raise AIProviderError("network", type(exc).__name__) from exc

        candidates = getattr(response, "candidates", None)
        if not candidates:
            raise AIInvalidOutput("respuesta_vacia")

        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) if content else None
        if not parts:
            raise AIInvalidOutput("respuesta_vacia")

        inline_data = getattr(parts[0], "inline_data", None)
        audio_data = getattr(inline_data, "data", None) if inline_data else None
        if not audio_data:
            raise AIInvalidOutput("respuesta_vacia")

        # Si ya viene con cabecera RIFF/WAVE (comportamiento de gemini-3.8-flash-tts)
        if audio_data.startswith(b"RIFF") and b"WAVE" in audio_data[:12]:
            return audio_data

        # Si viene en PCM crudo (modelos legacy 2.5/3.1-preview), empaquetar como WAV
        return pack_pcm_to_wav(audio_data)
