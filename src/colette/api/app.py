"""FastAPI application factory (NFR-USA-002)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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
from colette.db.session import close_engine, init_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the Colette FastAPI application."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # Startup: initialise DB engine.
        init_engine(settings)
        yield
        # Shutdown: dispose engine.
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
