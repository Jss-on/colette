"""API route assembly."""

from __future__ import annotations

from fastapi import APIRouter

from colette.api.routes.approvals import router as approvals_router
from colette.api.routes.artifacts import router as artifacts_router
from colette.api.routes.backlog import router as backlog_router
from colette.api.routes.health import router as health_router
from colette.api.routes.pipelines import router as pipelines_router
from colette.api.routes.projects import router as projects_router
from colette.api.routes.sprints import router as sprints_router
from colette.api.routes.ws import router as ws_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(pipelines_router, tags=["pipelines"])
api_router.include_router(approvals_router, prefix="/approvals", tags=["approvals"])
api_router.include_router(artifacts_router, tags=["artifacts"])
api_router.include_router(backlog_router, prefix="/projects", tags=["backlog"])
api_router.include_router(sprints_router, prefix="/projects", tags=["sprints"])
api_router.include_router(ws_router, tags=["websocket"])

# Health routes are at root level (no /api/v1 prefix).
__all__ = ["api_router", "health_router"]
