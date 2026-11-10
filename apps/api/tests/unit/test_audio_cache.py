"""Pruebas unitarias para la caché en memoria y single-flight de audios (HU 2)."""
import asyncio
import hashlib

import pytest

from app.ai.use_cases.exercise_audio.cache import AudioCache, make_cache_key


def test_make_cache_key_sha256_determinista() -> None:
    model = "gemini-3.8-flash-tts"
    voice = "Aoede"
    text = "Sentadilla con peso corporal. Paso 1: baja."

    key1 = make_cache_key(model, voice, text)
    key2 = make_cache_key(model, voice, text)

    assert key1 == key2
    expected = hashlib.sha256(f"{model}:{voice}:{text}".encode("utf-8")).hexdigest()
    assert key1 == expected
    # Sensibilidad a variaciones
    assert key1 != make_cache_key(model, "Puck", text)
    assert key1 != make_cache_key("otro-modelo", voice, text)


def test_audio_cache_lru_eviction() -> None:
    cache = AudioCache(max_entries=3)

    cache.set("k1", b"audio1")
    cache.set("k2", b"audio2")
    cache.set("k3", b"audio3")
    assert cache.size() == 3

    # Acceder a k1 la convierte en más reciente
    assert cache.get("k1") == b"audio1"

    # Insertar k4 debe desalojar la menos recientemente usada (k2)
    cache.set("k4", b"audio4")
    assert cache.size() == 3
    assert cache.get("k2") is None
    assert cache.get("k1") == b"audio1"
    assert cache.get("k3") == b"audio3"
    assert cache.get("k4") == b"audio4"


async def test_audio_cache_single_flight_concurrent_requests() -> None:
    cache = AudioCache(max_entries=10)
    calls = 0

    async def mock_compute() -> bytes:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return b"RIFF_AUDIO_DATA"

    # Dos peticiones concurrentes a la misma clave
    key = "test_key_concurrent"
    res1, res2 = await asyncio.gather(
        cache.get_or_compute(key, mock_compute),
        cache.get_or_compute(key, mock_compute),
    )

    assert res1 == b"RIFF_AUDIO_DATA"
    assert res2 == b"RIFF_AUDIO_DATA"
    assert calls == 1  # Single-flight: exactamente un cómputo ejecutado
    assert cache.get(key) == b"RIFF_AUDIO_DATA"


async def test_audio_cache_single_flight_failure_does_not_cache_error() -> None:
    cache = AudioCache(max_entries=10)
    calls = 0

    async def failing_compute() -> bytes:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        raise ValueError("error en proveedor")

    key = "test_key_failing"
    with pytest.raises(ValueError, match="error en proveedor"):
        await cache.get_or_compute(key, failing_compute)

    assert calls == 1
    # No debe haberse guardado nada en la caché
    assert cache.get(key) is None
    assert cache.size() == 0
