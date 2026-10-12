from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENV: Literal["development", "test", "production"] = "development"
    TZ: str = "America/Bogota"

    # Pooler de Supabase (runtime) y conexión directa (Alembic), ADR-02.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fitia_db"
    DATABASE_URL_DIRECT: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fitia_db"

    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # Versión del texto de consentimiento de tratamiento de datos (HU 8 / NFR-19).
    CONSENT_TEXT_VERSION: str = "2026-01"

    VERIFICATION_TOKEN_TTL_HOURS: int = 24
    SESSION_TTL_DAYS: int = 30
    # Expiración deslizante: last_seen_at/expires_at se actualizan como máximo una vez por intervalo.
    SESSION_TOUCH_INTERVAL_MINUTES: int = 10
    COOKIE_SECURE: bool = True

    MAIL_PROVIDER: Literal["console", "http"] = "console"
    MAIL_API_URL: str = "https://api.resend.com/emails"
    MAIL_API_KEY: str = ""
    MAIL_FROM: str = "FITIA <no-reply@fitia.univalle.edu.co>"

    # Límites de peticiones (ventana deslizante en memoria, por proceso).
    RATE_LIMIT_WINDOW_SECONDS: int = 900
    RATE_LIMIT_PER_IP: int = 30
    RATE_LIMIT_PER_EMAIL: int = 5
    # Login: por IP cuenta todos los intentos (alto: el campus comparte IP); por correo solo los fallidos.
    RATE_LIMIT_LOGIN_WINDOW_MINUTES: int = 15
    RATE_LIMIT_LOGIN_PER_IP: int = 100
    RATE_LIMIT_LOGIN_PER_EMAIL: int = 5

    # IA (ADR-07). Con ENV=production, AI_ENABLED=true exige AI_PROVIDER=gemini y una clave.
    AI_ENABLED: bool = True
    AI_PROVIDER: Literal["fake", "gemini"] = "fake"
    GEMINI_API_KEY: str = ""
    # Vacío = el modelo declarado en el YAML del prompt activo (hoy gemini-3.8-flash).
    GEMINI_MODEL: str = ""
    PROMPT_VERSION_WEEKLY_PLAN: str = "v1"
    AI_TIMEOUT_SECONDS: float = 20
    AI_TOTAL_BUDGET_SECONDS: float = 40
    AI_RETRY_MIN_REMAINING_SECONDS: float = 5
    AI_BREAKER_FAILURES: int = 5
    AI_BREAKER_WINDOW_SECONDS: float = 60
    AI_BREAKER_OPEN_SECONDS: float = 30

    # Plan semanal (HU 5)
    PLAN_MAX_GENERATIONS_PER_WEEK: int = 3  # 1 inicial + 2 regeneraciones
    PLAN_STALE_SECONDS: int = 90
    RATE_LIMIT_PLAN_GENERATE_PER_USER: int = 6
    RATE_LIMIT_PLAN_GENERATE_WINDOW_MINUTES: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _check_production_mailer(self) -> "Settings":
        # ConsoleMailer imprime el enlace con el token: nunca debe llegar a producción.
        if self.ENV == "production" and self.MAIL_PROVIDER == "console":
            raise ValueError("MAIL_PROVIDER=console no está permitido con ENV=production")
        # El adaptador falso de IA tampoco: en producción el plan debe venir de Gemini.
        if self.ENV == "production" and self.AI_ENABLED:
            if self.AI_PROVIDER == "fake":
                raise ValueError("AI_PROVIDER=fake no está permitido con ENV=production y AI_ENABLED=true")
            if not self.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY es obligatoria con ENV=production y AI_ENABLED=true")
        # Una generación viva nunca debe confundirse con una huérfana.
        if self.PLAN_STALE_SECONDS <= self.AI_TOTAL_BUDGET_SECONDS:
            raise ValueError("PLAN_STALE_SECONDS debe ser mayor que AI_TOTAL_BUDGET_SECONDS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
