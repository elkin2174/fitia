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
