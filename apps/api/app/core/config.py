from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    TZ: str = "America/Bogota"
    
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fitia_db"
    DIRECT_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/fitia_db"
    
    SECRET_KEY: str = "super_secret_dev_key_cambiar_en_produccion"
    SESSION_EXPIRE_DAYS: int = 30
    
    GEMINI_API_KEY: str = ""
    AI_PROVIDER: str = "fake"
    AI_ENABLED: bool = True
    
    MAILER_PROVIDER: str = "console"
    MAILER_API_KEY: str = ""
    MAILER_FROM: str = "no-reply@fitia.univalle.edu.co"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
