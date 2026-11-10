"""Puertos de IA por modalidad (ADR-07). Los casos de uso dependen de estos contratos, nunca de Gemini."""
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class TextRequest:
    system: str
    prompt: str
    input_data: Mapping[str, Any]  # solo las claves de la allowlist (PrivacyGuard)
    response_schema: Mapping[str, Any] | None
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    model: str = ""
    thinking_level: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


class TextGenerator(ABC):
    """Genera texto (aquí, JSON estructurado). Lanza AIProviderError o AIInvalidOutput."""

    model_name: str = "unknown"

    @abstractmethod
    async def generate(self, request: TextRequest) -> str: ...


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    voice: str
    model: str
    timeout_seconds: float
    extra: Mapping[str, Any] = field(default_factory=dict)


class SpeechSynthesizer(ABC):
    """Genera audio a partir de texto (TTS). Devuelve WAV ya empaquetado. Lanza AIProviderError o AIInvalidOutput."""

    model_name: str = "unknown"

    @abstractmethod
    async def synthesize(self, request: SpeechRequest) -> bytes: ...


class AudioProcessor(Protocol):
    """Contrato para una extensión futura (sin implementación)."""

    async def transcribe(self, audio: bytes, *, language: str) -> str: ...


class VisionAnalyzer(Protocol):
    """Contrato para una extensión futura (sin implementación)."""

    async def analyze(self, image: bytes, *, task: str) -> Mapping[str, Any]: ...
