import zoneinfo
from datetime import date, datetime, timedelta

BOGOTA_TZ = zoneinfo.ZoneInfo("America/Bogota")


class Clock:
    """Reloj inyectable para soportar pruebas deterministas de corte de día y festivos (ADR-10)."""

    def now(self) -> datetime:
        return datetime.now(BOGOTA_TZ)

    def today_date(self) -> date:
        return self.now().date()


class FrozenClock(Clock):
    """Reloj detenido que solo avanza cuando se le indica (pruebas de vencimiento)."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = (start or datetime.now(BOGOTA_TZ)).astimezone(BOGOTA_TZ)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta


_system_clock = Clock()


def get_clock() -> Clock:
    return _system_clock
