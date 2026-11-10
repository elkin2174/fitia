"""FakeSpeechAdapter: sintetizador determinista para local y pruebas (sin red).

Devuelve un WAV mínimo válido y determinista con cabecera estándar RIFF/WAVE.
En modo guion, cada llamada consume un comportamiento de la cola (éxito, error, espera, etc.).
"""
import asyncio
from collections import deque
import io
import wave

from app.ai.errors import AIInvalidOutput, AIProviderError, ProviderErrorKind
from app.ai.ports import SpeechRequest, SpeechSynthesizer


def make_deterministic_wav(duration_s: float = 0.5, sample_rate: int = 24000) -> bytes:
    """Genera bytes WAV válidos con silencio determinista de 16 bits mono."""
    num_frames = int(duration_s * sample_rate)
    pcm_data = b"\x00\x00" * num_frames
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


DEFAULT_DETERMINISTIC_WAV = make_deterministic_wav()


class SpeechBehavior:
    async def apply(self, request: SpeechRequest) -> bytes:
        raise NotImplementedError


class ValidSpeech(SpeechBehavior):
    def __init__(self, wav_bytes: bytes | None = None) -> None:
        self.wav_bytes = wav_bytes or DEFAULT_DETERMINISTIC_WAV

    async def apply(self, request: SpeechRequest) -> bytes:
        return self.wav_bytes


class FailSpeech(SpeechBehavior):
    def __init__(self, kind: ProviderErrorKind, detail: str = "simulado") -> None:
        self.kind = kind
        self.detail = detail

    async def apply(self, request: SpeechRequest) -> bytes:
        raise AIProviderError(self.kind, self.detail)


class EmptyOutputSpeech(SpeechBehavior):
    async def apply(self, request: SpeechRequest) -> bytes:
        raise AIInvalidOutput("respuesta_vacia")


class WaitSpeech(SpeechBehavior):
    """Espera controlada: avisa con `entered` y no responde hasta que el test active `release`."""

    def __init__(
        self,
        release: asyncio.Event,
        entered: asyncio.Event | None = None,
        then: SpeechBehavior | None = None,
    ) -> None:
        self.release = release
        self.entered = entered
        self.then = then or ValidSpeech()

    async def apply(self, request: SpeechRequest) -> bytes:
        if self.entered:
            self.entered.set()
        await self.release.wait()
        return await self.then.apply(request)


class FakeSpeechAdapter(SpeechSynthesizer):
    model_name = "fake-tts"

    def __init__(self) -> None:
        self.requests: list[SpeechRequest] = []  # espía del puerto
        self._script: deque[SpeechBehavior] = deque()

    def script(self, *behaviors: SpeechBehavior) -> None:
        self._script.extend(behaviors)

    @property
    def calls(self) -> int:
        return len(self.requests)

    async def synthesize(self, request: SpeechRequest) -> bytes:
        self.requests.append(request)
        behavior = self._script.popleft() if self._script else ValidSpeech()
        return await behavior.apply(request)
