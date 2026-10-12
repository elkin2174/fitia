import pytest

from app.core.errors import AppError
from app.core.rate_limit import RateLimiter


class _FakeTime:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value


def test_bloquea_al_superar_el_limite_y_libera_al_pasar_la_ventana() -> None:
    now = _FakeTime()
    limiter = RateLimiter(time_fn=now)

    for _ in range(3):
        limiter.hit("k", limit=3, window_seconds=60)
    with pytest.raises(AppError) as exc_info:
        limiter.hit("k", limit=3, window_seconds=60)
    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "RATE_LIMITED"
    assert exc_info.value.headers == {"Retry-After": "60"}

    now.value += 60
    limiter.hit("k", limit=3, window_seconds=60)


def test_claves_independientes() -> None:
    limiter = RateLimiter(time_fn=_FakeTime())

    limiter.hit("a", limit=1, window_seconds=60)
    limiter.hit("b", limit=1, window_seconds=60)


def test_check_no_registra_y_record_si() -> None:
    limiter = RateLimiter(time_fn=_FakeTime())

    for _ in range(5):
        limiter.check("k", limit=1, window_seconds=60)
    limiter.record("k", window_seconds=60)
    with pytest.raises(AppError):
        limiter.check("k", limit=1, window_seconds=60)


def test_clear_reinicia_el_contador() -> None:
    limiter = RateLimiter(time_fn=_FakeTime())
    limiter.hit("k", limit=1, window_seconds=60)

    limiter.clear("k")

    limiter.hit("k", limit=1, window_seconds=60)
