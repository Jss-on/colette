"""FastAPI dependency injection — DB sessions, auth, runner."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from colette.config import Settings
from colette.db.session import get_db as get_db  # re-export for routes
from colette.orchestrator.runner import PipelineRunner
from colette.security.rbac import Permission, Role

# ---------------------------------------------------------------------------
# Settings (cached singleton)
# ---------------------------------------------------------------------------

_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    username: str
    role: Role


async def get_current_user(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> CurrentUser:
    """Extract and validate the current user from the API key header.

    For v1.0 we use a simple API-key-to-user lookup.  If no API key is
    provided and RBAC is disabled, fall back to a default admin user.
    """
    if not settings.rbac_enabled:
        return CurrentUser(
            user_id="default",
            username="admin",
            role=Role.SYSTEM_ADMINISTRATOR,
        )

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    from colette.db.repositories import UserRepository

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    repo = UserRepository(db)
    user = await repo.get_by_api_key_hash(key_hash)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    try:
        role = Role(user.role)
    except ValueError:
        role = Role.OBSERVER

    return CurrentUser(
        user_id=str(user.id),
        username=user.username,
        role=role,
    )


# ---------------------------------------------------------------------------
# RBAC dependency factory
# ---------------------------------------------------------------------------


def require_role(permission: Permission):  # type: ignore[no-untyped-def]
    """Return a FastAPI dependency that checks the user has *permission*."""

    async def _check(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        from colette.security.rbac import has_permission

        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission.value}' required",
            )
        return user

    return _check


# ---------------------------------------------------------------------------
# Pipeline runner (singleton)
# ---------------------------------------------------------------------------

_runner: PipelineRunner | None = None


def get_pipeline_runner(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> PipelineRunner:
    global _runner
    if _runner is None:
        _runner = PipelineRunner(settings)
    return _runner
