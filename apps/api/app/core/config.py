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

    GEMINI_API_KEY: str = ""
    AI_PROVIDER: str = "fake"
    AI_ENABLED: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _check_production_mailer(self) -> "Settings":
        # ConsoleMailer imprime el enlace con el token: nunca debe llegar a producción.
        if self.ENV == "production" and self.MAIL_PROVIDER == "console":
            raise ValueError("MAIL_PROVIDER=console no está permitido con ENV=production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
