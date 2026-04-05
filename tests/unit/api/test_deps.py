"""Tests for FastAPI dependency injection helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.api.deps import (
    CurrentUser,
    get_pipeline_runner,
    get_settings,
    require_role,
)
from colette.config import Settings
from colette.security.rbac import Permission, Role


class TestGetSettings:
    def test_returns_settings_instance(self) -> None:
        # Reset the cached singleton
        import colette.api.deps as deps_mod

        deps_mod._settings = None
        try:
            s = get_settings()
            assert isinstance(s, Settings)
        finally:
            deps_mod._settings = None

    def test_caches_singleton(self) -> None:
        import colette.api.deps as deps_mod

        deps_mod._settings = None
        try:
            s1 = get_settings()
            s2 = get_settings()
            assert s1 is s2
        finally:
            deps_mod._settings = None


class TestCurrentUser:
    def test_frozen_dataclass(self) -> None:
        user = CurrentUser(user_id="u1", username="admin", role=Role.SYSTEM_ADMINISTRATOR)
        assert user.user_id == "u1"
        assert user.username == "admin"
        assert user.role == Role.SYSTEM_ADMINISTRATOR

    def test_frozen_prevents_mutation(self) -> None:
        user = CurrentUser(user_id="u1", username="admin", role=Role.SYSTEM_ADMINISTRATOR)
        with pytest.raises(AttributeError):
            user.username = "hacker"  # type: ignore[misc]


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_rbac_disabled_returns_default_admin(self) -> None:
        from colette.api.deps import get_current_user

        settings = Settings(rbac_enabled=False)
        db = AsyncMock()
        user = await get_current_user(x_api_key=None, db=db, settings=settings)
        assert user.user_id == "default"
        assert user.username == "admin"
        assert user.role == Role.SYSTEM_ADMINISTRATOR

    @pytest.mark.asyncio
    async def test_rbac_enabled_no_key_raises_401(self) -> None:
        from fastapi import HTTPException

        from colette.api.deps import get_current_user

        settings = Settings(rbac_enabled=True)
        db = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(x_api_key=None, db=db, settings=settings)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_rbac_enabled_invalid_key_raises_401(self) -> None:
        from fastapi import HTTPException

        from colette.api.deps import get_current_user

        settings = Settings(rbac_enabled=True)
        db = AsyncMock()

        # UserRepository is imported inside the function body
        mock_repo = AsyncMock()
        mock_repo.get_by_api_key_hash = AsyncMock(return_value=None)
        with patch("colette.db.repositories.UserRepository", return_value=mock_repo):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(x_api_key="bad-key", db=db, settings=settings)
            assert exc_info.value.status_code == 401


class TestGetPipelineRunner:
    def test_returns_runner(self) -> None:
        import colette.api.deps as deps_mod

        deps_mod._runner = None
        try:
            runner = get_pipeline_runner(Settings())
            assert runner is not None
        finally:
            deps_mod._runner = None

    def test_caches_singleton(self) -> None:
        import colette.api.deps as deps_mod

        deps_mod._runner = None
        try:
            r1 = get_pipeline_runner(Settings())
            r2 = get_pipeline_runner(Settings())
            assert r1 is r2
        finally:
            deps_mod._runner = None


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_allows_with_permission(self) -> None:
        check = require_role(Permission.SUBMIT_PROJECT)
        user = CurrentUser(user_id="u1", username="requestor", role=Role.PROJECT_REQUESTOR)
        result = await check(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_denies_without_permission(self) -> None:
        from fastapi import HTTPException

        check = require_role(Permission.MANAGE_CONFIG)
        user = CurrentUser(user_id="u1", username="viewer", role=Role.OBSERVER)
        with pytest.raises(HTTPException) as exc_info:
            await check(user=user)
        assert exc_info.value.status_code == 403
