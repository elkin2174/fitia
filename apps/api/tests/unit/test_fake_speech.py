"""Pruebas unitarias para FakeSpeechAdapter (HU 1)."""
import asyncio
import io
import wave

import pytest

from app.ai.adapters.fake_speech import (
    DEFAULT_DETERMINISTIC_WAV,
    EmptyOutputSpeech,
    FailSpeech,
    FakeSpeechAdapter,
    ValidSpeech,
    WaitSpeech,
)
from app.ai.errors import AIInvalidOutput, AIProviderError
from app.ai.ports import SpeechRequest


async def test_fake_speech_default_generates_valid_wav() -> None:
    adapter = FakeSpeechAdapter()
    req = SpeechRequest(text="Hola mundo", voice="Aoede", model="fake-tts", timeout_seconds=10.0)

    audio = await adapter.synthesize(req)

    assert audio.startswith(b"RIFF")
    assert b"WAVE" in audio[:12]
    with wave.open(io.BytesIO(audio), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 24000
        assert wf.getsampwidth() == 2
    assert adapter.calls == 1
    assert adapter.requests[0].text == "Hola mundo"


async def test_fake_speech_mode_script_fail() -> None:
    adapter = FakeSpeechAdapter()
    adapter.script(FailSpeech("rate_limited", "429 simulado"))

    req = SpeechRequest(text="Texto", voice="Aoede", model="fake-tts", timeout_seconds=5.0)

    with pytest.raises(AIProviderError) as exc:
        await adapter.synthesize(req)
    assert exc.value.kind == "rate_limited"


async def test_fake_speech_mode_script_empty_output() -> None:
    adapter = FakeSpeechAdapter()
    adapter.script(EmptyOutputSpeech())

    req = SpeechRequest(text="Texto", voice="Aoede", model="fake-tts", timeout_seconds=5.0)

    with pytest.raises(AIInvalidOutput):
        await adapter.synthesize(req)


async def test_fake_speech_mode_script_wait() -> None:
    adapter = FakeSpeechAdapter()
    release = asyncio.Event()
    entered = asyncio.Event()
    adapter.script(WaitSpeech(release=release, entered=entered))

    req = SpeechRequest(text="Espera", voice="Aoede", model="fake-tts", timeout_seconds=5.0)

    task = asyncio.create_task(adapter.synthesize(req))
    await entered.wait()
    assert not task.done()

    release.set()
    res = await task
    assert res == DEFAULT_DETERMINISTIC_WAV
