"""Database engine, session factory, and advanced-alchemy plugin configuration."""

from typing import AsyncIterator

from advanced_alchemy.config import AsyncSessionConfig
from advanced_alchemy.extensions.litestar.plugins.init.config import SQLAlchemyAsyncConfig
from advanced_alchemy.extensions.litestar.plugins.init.plugin import SQLAlchemyInitPlugin
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


# ── Async engine ──────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# ── Session factory ───────────────────────────────────────────────────────────

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=True,
)

# ── Dependency injection generator ────────────────────────────────────────────

async def provide_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


# ── advanced-alchemy config & plugin ──────────────────────────────────────────

session_config = AsyncSessionConfig(
    expire_on_commit=False,
    autoflush=True,
)

config = SQLAlchemyAsyncConfig(
    connection_string=settings.database_url,
    session_config=session_config,
    create_all=False,
    enable_touch_updated_timestamp_listener=True,
)

plugin = SQLAlchemyInitPlugin(config=config)