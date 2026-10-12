import math
import time
from collections import deque
from collections.abc import Callable

from app.core.config import Settings
from app.core.errors import AppError


class RateLimiter:
    """Ventana deslizante en memoria. Es por proceso: con varias instancias usar un almacén compartido."""

    def __init__(self, time_fn: Callable[[], float] = time.monotonic) -> None:
        self._time = time_fn
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        """Lanza 429 si la clave ya alcanzó el límite, sin registrar un intento nuevo."""
        now = self._time()
        hits = self._current(key, now, window_seconds)
        if len(hits) >= limit:
            retry_after = max(1, math.ceil(hits[0] + window_seconds - now))
            raise AppError(
                429,
                "RATE_LIMITED",
                "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
                headers={"Retry-After": str(retry_after)},
            )

    def record(self, key: str, window_seconds: int) -> None:
        now = self._time()
        self._current(key, now, window_seconds).append(now)
        if len(self._hits) > 10_000:
            self._prune(now, window_seconds)

    def hit(self, key: str, limit: int, window_seconds: int) -> None:
        self.check(key, limit, window_seconds)
        self.record(key, window_seconds)

    def clear(self, key: str) -> None:
        self._hits.pop(key, None)

    def _current(self, key: str, now: float, window_seconds: int) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        return hits

    def _prune(self, now: float, window_seconds: int) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - window_seconds]:
            del self._hits[key]

    def reset(self) -> None:
        self._hits.clear()


_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _limiter


def enforce_ip_and_email_limits(
    limiter: RateLimiter, settings: Settings, scope: str, client_ip: str, email_key: str
) -> None:
    window = settings.RATE_LIMIT_WINDOW_SECONDS
    limiter.hit(f"{scope}:ip:{client_ip}", settings.RATE_LIMIT_PER_IP, window)
    limiter.hit(f"{scope}:email:{email_key}", settings.RATE_LIMIT_PER_EMAIL, window)
