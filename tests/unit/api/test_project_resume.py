"""Tests for project resume endpoint — crash recovery from awaiting_approval."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from colette.api.routes.projects import resume_project


def _fake_project(status: str = "interrupted") -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.name = "test-proj"
    p.status = status
    p.user_request = "Build something"
    p.description = "Build something"
    p.created_at = "2026-04-05T10:00:00Z"
    p.updated_at = "2026-04-05T10:00:00Z"
    return p


def _fake_run(project_id: uuid.UUID) -> MagicMock:
    r = MagicMock()
    r.id = uuid.uuid4()
    r.project_id = project_id
    r.thread_id = "thread-1"
    return r


@pytest.mark.asyncio
async def test_resume_from_awaiting_approval_no_pending() -> None:
    """When project is awaiting_approval but approvals are lost, resume should work."""
    project = _fake_project("awaiting_approval")
    run = _fake_run(project.id)

    project_repo = AsyncMock()
    project_repo.get_by_id.return_value = project
    project_repo.update_status = AsyncMock()

    approval_repo = AsyncMock()
    approval_repo.list_pending_by_run.return_value = []  # No pending approvals.

    run_repo = AsyncMock()
    run_repo.list_for_project.return_value = [run]

    db = AsyncMock()
    db.commit = AsyncMock()

    runner = MagicMock()
    runner._active = {}

    bg = MagicMock()

    with (
        patch("colette.api.routes.projects.ProjectRepository", return_value=project_repo),
        patch(
            "colette.api.routes.projects.ApprovalRecordRepository",
            return_value=approval_repo,
        ),
        patch(
            "colette.api.routes.projects.PipelineRunRepository",
            return_value=run_repo,
        ),
        patch("colette.api.routes.projects.project_status_registry") as mock_reg,
        patch("colette.api.routes.approvals._resume_pipeline_bg"),
        patch("colette.api.routes.projects.require_role", return_value=lambda: None),
    ):
        # After update, re-fetch returns updated project.
        updated = _fake_project("running")
        updated.id = project.id
        project_repo.get_by_id.side_effect = [project, updated]

        await resume_project(
            project_id=project.id,
            background_tasks=bg,
            user=MagicMock(),
            db=db,
            runner=runner,
        )

    project_repo.update_status.assert_awaited_once()
    mock_reg.mark.assert_called_once()
    # Should use checkpoint-based resume, not fresh start.
    bg.add_task.assert_called_once()
    call_args = bg.add_task.call_args
    assert call_args[0][3] == run.thread_id  # thread_id passed to _resume_pipeline_bg


@pytest.mark.asyncio
async def test_resume_uses_checkpoint_when_thread_exists() -> None:
    """Resume should rehydrate from checkpoint, not start fresh."""
    project = _fake_project("interrupted")
    run = _fake_run(project.id)
    run.thread_id = "checkpoint-thread-42"

    project_repo = AsyncMock()
    project_repo.update_status = AsyncMock()

    run_repo = AsyncMock()
    run_repo.list_for_project.return_value = [run]

    db = AsyncMock()
    db.commit = AsyncMock()

    runner = MagicMock()
    runner._active = {}

    bg = MagicMock()

    with (
        patch("colette.api.routes.projects.ProjectRepository", return_value=project_repo),
        patch(
            "colette.api.routes.projects.PipelineRunRepository",
            return_value=run_repo,
        ),
        patch("colette.api.routes.projects.project_status_registry"),
        patch("colette.api.routes.approvals._resume_pipeline_bg"),
        patch("colette.api.routes.projects.require_role", return_value=lambda: None),
    ):
        updated = _fake_project("running")
        updated.id = project.id
        project_repo.get_by_id.side_effect = [project, updated]

        await resume_project(
            project_id=project.id,
            background_tasks=bg,
            user=MagicMock(),
            db=db,
            runner=runner,
        )

    # Verify _resume_pipeline_bg was scheduled with the correct thread_id.
    bg.add_task.assert_called_once()
    call_args = bg.add_task.call_args[0]
    assert call_args[3] == "checkpoint-thread-42"


@pytest.mark.asyncio
async def test_resume_starts_fresh_when_no_prior_run() -> None:
    """Resume should start fresh when no pipeline run exists."""
    project = _fake_project("failed")

    project_repo = AsyncMock()
    project_repo.update_status = AsyncMock()

    run_repo = AsyncMock()
    run_repo.list_for_project.return_value = []  # No prior runs.

    db = AsyncMock()
    db.commit = AsyncMock()

    runner = MagicMock()
    runner._active = {}

    bg = MagicMock()

    with (
        patch("colette.api.routes.projects.ProjectRepository", return_value=project_repo),
        patch(
            "colette.api.routes.projects.PipelineRunRepository",
            return_value=run_repo,
        ),
        patch("colette.api.routes.projects.project_status_registry"),
        patch("colette.api.routes.projects._run_pipeline_bg"),
        patch("colette.api.routes.projects.require_role", return_value=lambda: None),
    ):
        updated = _fake_project("running")
        updated.id = project.id
        project_repo.get_by_id.side_effect = [project, updated]

        await resume_project(
            project_id=project.id,
            background_tasks=bg,
            user=MagicMock(),
            db=db,
            runner=runner,
        )

    # Should fall back to fresh start.
    bg.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_resume_from_awaiting_approval_with_pending() -> None:
    """When project is awaiting_approval and approvals exist, resume should fail."""
    from fastapi import HTTPException

    project = _fake_project("awaiting_approval")
    run = _fake_run(project.id)

    project_repo = AsyncMock()
    project_repo.get_by_id.return_value = project

    pending_approval = MagicMock()
    approval_repo = AsyncMock()
    approval_repo.list_pending_by_run.return_value = [pending_approval]

    run_repo = AsyncMock()
    run_repo.list_for_project.return_value = [run]

    db = AsyncMock()
    runner = MagicMock()
    runner._active = {}
    bg = MagicMock()

    with (
        patch("colette.api.routes.projects.ProjectRepository", return_value=project_repo),
        patch(
            "colette.api.routes.projects.ApprovalRecordRepository",
            return_value=approval_repo,
        ),
        patch(
            "colette.api.routes.projects.PipelineRunRepository",
            return_value=run_repo,
        ),
        patch("colette.api.routes.projects.require_role", return_value=lambda: None),
        pytest.raises(HTTPException) as exc_info,
    ):
        await resume_project(
            project_id=project.id,
            background_tasks=bg,
            user=MagicMock(),
            db=db,
            runner=runner,
        )

    assert exc_info.value.status_code == 409
    assert "awaiting approval" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_resume_completed_project_blocked() -> None:
    """Completed projects cannot be resumed."""
    from fastapi import HTTPException

    project = _fake_project("completed")
    project_repo = AsyncMock()
    project_repo.get_by_id.return_value = project

    db = AsyncMock()
    runner = MagicMock()
    bg = MagicMock()

    with (
        patch("colette.api.routes.projects.ProjectRepository", return_value=project_repo),
        patch("colette.api.routes.projects.require_role", return_value=lambda: None),
        pytest.raises(HTTPException) as exc_info,
    ):
        await resume_project(
            project_id=project.id,
            background_tasks=bg,
            user=MagicMock(),
            db=db,
            runner=runner,
        )

    assert exc_info.value.status_code == 409
