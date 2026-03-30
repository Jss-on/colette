"""Tests for repository layer (unit tests with mocked sessions)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from colette.db.models import Project, User
from colette.db.repositories import ProjectRepository, UserRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_project_repo_create(mock_session: AsyncMock) -> None:
    repo = ProjectRepository(mock_session)
    project = await repo.create(
        name="Test Project",
        user_request="Build something",
    )
    assert isinstance(project, Project)
    assert project.name == "Test Project"
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_project_repo_get_by_id(mock_session: AsyncMock) -> None:
    pid = uuid.uuid4()
    mock_session.get = AsyncMock(return_value=Project(id=pid, name="Found"))
    repo = ProjectRepository(mock_session)
    result = await repo.get_by_id(pid)
    assert result is not None
    assert result.name == "Found"


@pytest.mark.asyncio
async def test_project_repo_get_by_id_not_found(mock_session: AsyncMock) -> None:
    mock_session.get = AsyncMock(return_value=None)
    repo = ProjectRepository(mock_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_user_repo_create(mock_session: AsyncMock) -> None:
    repo = UserRepository(mock_session)
    user = await repo.create(username="testuser", role="observer")
    assert isinstance(user, User)
    assert user.username == "testuser"
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_project_repo_update_status(mock_session: AsyncMock) -> None:
    repo = ProjectRepository(mock_session)
    await repo.update_status(uuid.uuid4(), "completed")
    mock_session.execute.assert_awaited_once()
