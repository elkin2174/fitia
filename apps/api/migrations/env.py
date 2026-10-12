import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.db import POOLER_CONNECT_ARGS, Base, to_asyncpg_url
from app.modules.auth import models  # noqa: F401  (registra las tablas en Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    # Las pruebas inyectan su propia URL; en el resto de casos se usa la conexión directa.
    return config.attributes.get("database_url") or get_settings().DATABASE_URL_DIRECT


def run_migrations_offline() -> None:
    context.configure(url=to_asyncpg_url(_database_url()), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(
        to_asyncpg_url(_database_url()), poolclass=pool.NullPool, connect_args=POOLER_CONNECT_ARGS
    )
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
