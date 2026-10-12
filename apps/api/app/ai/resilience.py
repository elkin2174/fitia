"""Circuit breaker en memoria (por proceso) y tiempo inyectable para reintentos deterministas."""
import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable

TimeFn = Callable[[], float]
SleepFn = Callable[[float], Awaitable[None]]

RETRY_BACKOFF_SECONDS = 0.5


class CircuitBreaker:
    """Se abre tras N fallos de DISPONIBILIDAD dentro de una ventana. Abierto, no deja pasar llamadas.
    Pasado `open_seconds` deja pasar UN intento de prueba: si funciona se cierra; si falla se reabre."""

    def __init__(self, failures: int, window_seconds: float, open_seconds: float, time_fn: TimeFn = time.monotonic):
        self._threshold = failures
        self._window = window_seconds
        self._open_seconds = open_seconds
        self._time = time_fn
        self._failures: deque[float] = deque()
        self._opened_at: float | None = None
        self._trial_in_flight = False

    @property
    def is_open(self) -> bool:
        return self._opened_at is not None and self._time() - self._opened_at < self._open_seconds

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if self._time() - self._opened_at < self._open_seconds or self._trial_in_flight:
            return False
        self._trial_in_flight = True  # semiabierto: un único intento de prueba
        return True

    def record_success(self) -> None:
        self._failures.clear()
        self._opened_at = None
        self._trial_in_flight = False

    def record_failure(self) -> None:
        now = self._time()
        if self._trial_in_flight:  # falló el intento de prueba: se reabre
            self._trial_in_flight = False
            self._opened_at = now
            return
        self._failures.append(now)
        while self._failures and self._failures[0] <= now - self._window:
            self._failures.popleft()
        if len(self._failures) >= self._threshold:
            self._opened_at = now
            self._failures.clear()


async def real_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)
