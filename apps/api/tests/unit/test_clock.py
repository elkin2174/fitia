from datetime import datetime, timedelta, timezone

from app.core.clock import BOGOTA_TZ, Clock, FrozenClock


def test_clock_usa_zona_bogota() -> None:
    assert Clock().now().utcoffset() == timedelta(hours=-5)


def test_frozen_clock_avanza_solo_cuando_se_indica() -> None:
    clock = FrozenClock(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))

    assert clock.now() == datetime(2026, 1, 1, 7, 0, tzinfo=BOGOTA_TZ)
    clock.advance(timedelta(hours=24, seconds=1))
    assert clock.now() == datetime(2026, 1, 2, 7, 0, 1, tzinfo=BOGOTA_TZ)
    assert clock.today_date().isoformat() == "2026-01-02"
