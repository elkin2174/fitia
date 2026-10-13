import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.db import to_asyncpg_url
from app.core.mailer import ConsoleMailer, HttpMailer, build_mailer


def test_produccion_no_admite_console_mailer() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENV="production", MAIL_PROVIDER="console")


def test_build_mailer_segun_configuracion() -> None:
    assert isinstance(build_mailer(Settings(_env_file=None, MAIL_PROVIDER="console")), ConsoleMailer)
    assert isinstance(build_mailer(Settings(_env_file=None, MAIL_PROVIDER="http", MAIL_API_KEY="k")), HttpMailer)


def test_to_asyncpg_url_normaliza_urls_de_supabase() -> None:
    url = to_asyncpg_url("postgresql://u:p@db.supabase.co:5432/postgres?sslmode=require")

    assert url == "postgresql+asyncpg://u:p@db.supabase.co:5432/postgres?ssl=require"


@pytest.mark.parametrize(
    "overrides",
    [
        {"AI_PROVIDER": "fake", "GEMINI_API_KEY": "k"},
        {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": ""},
    ],
)
def test_produccion_con_ia_exige_gemini_y_clave(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENV="production", MAIL_PROVIDER="http", AI_ENABLED=True, **overrides)


def test_produccion_con_gemini_y_clave_arranca() -> None:
    Settings(_env_file=None, ENV="production", MAIL_PROVIDER="http", AI_PROVIDER="gemini", GEMINI_API_KEY="k")


def test_produccion_con_ia_deshabilitada_no_exige_clave() -> None:
    Settings(_env_file=None, ENV="production", MAIL_PROVIDER="http", AI_ENABLED=False)


def test_stale_debe_superar_el_presupuesto_de_la_ia() -> None:
    with pytest.raises(ValidationError, match="PLAN_STALE_SECONDS"):
        Settings(_env_file=None, PLAN_STALE_SECONDS=30, AI_TOTAL_BUDGET_SECONDS=40)
