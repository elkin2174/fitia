import asyncio
import os
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.clock import BOGOTA_TZ, FrozenClock, get_clock
from app.core.config import Settings, get_settings
from app.core.db import create_engine, get_session
from app.core.mailer import get_mailer
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.main import app
from seeds.load_academic_programs import load_programs, read_programs
from tests.fakes import FakeMailer

API_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/fitia_test"
)
CSRF_HEADERS = {"X-Requested-With": "fitia"}
FRONTEND_URL = "https://fitia.test"


async def _reset_schema() -> None:
    engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


async def _seed() -> None:
    engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await load_programs(conn, read_programs())
    await engine.dispose()


@pytest.fixture(scope="session")
def migrated_database() -> str:
    """Esquema limpio + migraciones reales de Alembic + seed, una vez por sesión de pruebas."""
    asyncio.run(_reset_schema())
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    config.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(config, "head")
    asyncio.run(_seed())
    return TEST_DATABASE_URL


@pytest.fixture
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(migrated_database, poolclass=NullPool)
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users CASCADE"))
    await engine.dispose()


@pytest.fixture
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def db(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Sesión para que las pruebas inspeccionen la BD directamente."""
    async with sessionmaker() as session:
        yield session


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 10, 12, 9, 0, 0, tzinfo=BOGOTA_TZ))


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        ENV="test",
        FRONTEND_BASE_URL=FRONTEND_URL,
        CONSENT_TEXT_VERSION="2026-01",
        COOKIE_SECURE=True,
        MAIL_PROVIDER="console",
        RATE_LIMIT_PER_IP=30,
        RATE_LIMIT_PER_EMAIL=5,
    )


@pytest.fixture
async def client(
    sessionmaker: async_sessionmaker[AsyncSession],
    clock: FrozenClock,
    mailer: FakeMailer,
    settings: Settings,
) -> AsyncIterator[httpx.AsyncClient]:
    async def _session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    limiter = RateLimiter()
    app.dependency_overrides.update(
        {
            get_session: _session,
            get_clock: lambda: clock,
            get_mailer: lambda: mailer,
            get_settings: lambda: settings,
            get_rate_limiter: lambda: limiter,
        }
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=CSRF_HEADERS) as c:
        yield c
    app.dependency_overrides.clear()


def valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "nickname": "Pantera",
        "email": "ana.gomez@correounivalle.edu.co",
        "password": "contrasena-segura",
        "program_code": "ING-SIS",
        "accepted_terms": True,
    }
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not _OMIT}


_OMIT = object()


@pytest.fixture
def omit() -> object:
    """Marcador para quitar un campo del payload: valid_payload(program_code=omit)."""
    return _OMIT


@pytest.fixture
def register(client: httpx.AsyncClient) -> Callable[..., Any]:
    async def _register(**overrides: Any) -> httpx.Response:
        return await client.post("/api/v1/auth/register", json=valid_payload(**overrides))

    return _register
