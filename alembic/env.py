import asyncio
from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection
from alembic import context

config = context.config
fileConfig(config.config_file_name)

from app.core.config import settings
from app.db.base import Base

# Import all models so Alembic autogenerate detects them
from app.db.models.feature_flag import FeatureFlag, FlagOverride  # noqa: F401
from app.db.models.api_key import APIKey  # noqa: F401

target_metadata = Base.metadata

def run_migrations_offline():
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    url = settings.DATABASE_URL

    # Async drivers (Postgres asyncpg or SQLite aiosqlite)
    if url.startswith("postgresql+asyncpg") or "aiosqlite" in url:
        from sqlalchemy.ext.asyncio import create_async_engine
        async_engine = create_async_engine(url, poolclass=pool.NullPool)
        async def _run():
            async with async_engine.connect() as connection:
                await connection.run_sync(do_run_migrations)
            await async_engine.dispose()
        asyncio.run(_run())
        return

    # Fallback: synchronous engine (sqlite, sync pg)
    sync_url = url
    if "+aiosqlite" in sync_url:
        sync_url = sync_url.replace("+aiosqlite", "")
    if "+asyncpg" in sync_url:
        sync_url = sync_url.replace("+asyncpg", "")
    engine = create_engine(sync_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        do_run_migrations(connection)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
