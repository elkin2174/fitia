from datetime import datetime
import zoneinfo

BOGOTA_TZ = zoneinfo.ZoneInfo("America/Bogota")

class Clock:
    """Reloj inyectable para soportar pruebas deterministas de corte de día y festivos (ADR-10)."""
    @staticmethod
    def now() -> datetime:
        return datetime.now(BOGOTA_TZ)

    @staticmethod
    def today_date():
        return Clock.now().date()
