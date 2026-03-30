"""Health and readiness endpoints (NFR-REL-008)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from colette import __version__
from colette.api.schemas import HealthCheck, HealthResponse
from colette.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Liveness probe — returns 200 if the process is running."""
    return HealthResponse(status="healthy", version=__version__)


@router.get("/ready", response_model=HealthResponse)
async def readiness(db: AsyncSession = Depends(get_db)) -> HealthResponse:  # noqa: B008
    """Readiness probe — checks DB connectivity."""
    checks: list[HealthCheck] = []
    overall = "healthy"

    # Database check
    t0 = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        latency = (time.monotonic() - t0) * 1000
        checks.append(HealthCheck(name="database", status="ok", latency_ms=round(latency, 2)))
    except Exception:
        checks.append(HealthCheck(name="database", status="unhealthy"))
        overall = "degraded"

    return HealthResponse(status=overall, version=__version__, checks=checks)
