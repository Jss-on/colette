"""Async SQLAlchemy engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from colette.config import Settings

# Module-level singletons — initialised via ``init_engine()``.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_async_engine_from_settings(settings: Settings) -> AsyncEngine:
    """Create and return an async engine from application settings."""
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
        echo=settings.debug,
    )


def init_engine(settings: Settings) -> AsyncEngine:
    """Initialise the module-level engine and session factory.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine_from_settings(settings)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def close_engine() -> None:
    """Dispose of the module-level engine (call on shutdown)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


@asynccontextmanager
async def async_session() -> AsyncGenerator[AsyncSession]:
    """Yield a request-scoped async session."""
    if _session_factory is None:
        msg = "Database engine not initialised — call init_engine() first."
        raise RuntimeError(msg)
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency that yields an async session."""
    async with async_session() as session:
        yield session
