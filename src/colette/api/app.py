"""FastAPI application factory (NFR-USA-002)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from colette import __version__
from colette.api.middleware import (
    GracefulDegradationMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
)
from colette.api.routes import api_router, health_router
from colette.config import Settings
from colette.db.cleanup import cleanup_stale_runs
from colette.db.session import async_session, close_engine, init_engine

logger = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the Colette FastAPI application."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        from colette.api.deps import get_pipeline_runner

        # Startup: initialise DB engine.
        init_engine(settings)

        # Clean up orphaned pipeline runs from previous server lifetime.
        try:
            async with async_session() as session:
                cleaned = await cleanup_stale_runs(session)
                if cleaned:
                    logger.warning("startup.stale_runs_cleaned", count=cleaned)
        except Exception as exc:
            # Non-fatal: the server can still start even if cleanup fails
            # (e.g. DB tables don't exist yet on first run).
            logger.error("startup.cleanup_failed", error=str(exc))

        # Initialise the pipeline runner (opens Postgres checkpoint pool
        # when checkpoint_backend="postgres").
        runner = get_pipeline_runner(settings)
        await runner.asetup()

        yield

        # Shutdown: close checkpoint pool, then dispose DB engine.
        await runner.ashutdown()
        await close_engine()

    app = FastAPI(
        title="Colette API",
        description="Multi-agent SDLC system REST API",
        version=__version__,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first).
    app.add_middleware(GracefulDegradationMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)  # type: ignore[arg-type]
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes.
    app.include_router(health_router)
    app.include_router(api_router)

    return app
