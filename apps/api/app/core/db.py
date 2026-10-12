import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def to_asyncpg_url(url: str) -> str:
    """Normaliza una URL de Postgres (p. ej. la que entrega Supabase) para el driver asyncpg."""
    parsed = make_url(url)
    if parsed.drivername in ("postgres", "postgresql", "postgresql+psycopg2"):
        parsed = parsed.set(drivername="postgresql+asyncpg")
    query = dict(parsed.query)
    if "sslmode" in query:  # asyncpg usa `ssl` en lugar de `sslmode`
        query["ssl"] = query.pop("sslmode")
        parsed = parsed.set(query=query)
    return parsed.render_as_string(hide_password=False)


# El pooler de Supabase (PgBouncer en modo transacción) no soporta prepared statements
# cacheados: se desactivan ambas cachés y se usan nombres únicos por sentencia.
POOLER_CONNECT_ARGS: dict[str, Any] = {
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0,
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
}


def create_engine(url: str, **kwargs: Any) -> AsyncEngine:
    return create_async_engine(
        to_asyncpg_url(url),
        connect_args=POOLER_CONNECT_ARGS,
        pool_pre_ping=True,
        **kwargs,
    )


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _engine, _sessionmaker
    if _sessionmaker is None:
        _engine = create_engine(get_settings().DATABASE_URL, pool_size=5, max_overflow=5)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """Una sesión por request; lo no confirmado se revierte al cerrar."""
    async with get_sessionmaker()() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Fábrica de sesiones para trabajos fuera del request (p. ej. la generación del plan)."""
    return get_sessionmaker()
