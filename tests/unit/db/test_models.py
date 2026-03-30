"""Tests for database ORM models."""

from __future__ import annotations

import uuid

from colette.db.models import (
    Artifact,
    PipelineRun,
    Project,
    StageExecution,
    User,
    _new_uuid,
    _utcnow,
)


def test_new_uuid_returns_uuid4() -> None:
    result = _new_uuid()
    assert isinstance(result, uuid.UUID)
    assert result.version == 4


def test_utcnow_returns_datetime() -> None:
    from datetime import datetime

    result = _utcnow()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_user_tablename() -> None:
    assert User.__tablename__ == "users"


def test_project_tablename() -> None:
    assert Project.__tablename__ == "projects"


def test_pipeline_run_tablename() -> None:
    assert PipelineRun.__tablename__ == "pipeline_runs"


def test_stage_execution_tablename() -> None:
    assert StageExecution.__tablename__ == "stage_executions"


def test_artifact_tablename() -> None:
    assert Artifact.__tablename__ == "artifacts"


def test_user_model_with_explicit_defaults() -> None:
    user = User(username="testuser", role="observer", api_key_hash="")
    assert user.username == "testuser"
    assert user.role == "observer"


def test_project_model_with_explicit_defaults() -> None:
    project = Project(
        name="Untitled",
        status="created",
        user_request="Build a TODO app",
        description="",
    )
    assert project.name == "Untitled"
    assert project.status == "created"
    assert project.user_request == "Build a TODO app"


def test_pipeline_run_model_with_explicit_defaults() -> None:
    pid = uuid.uuid4()
    run = PipelineRun(
        project_id=pid,
        thread_id="test-thread",
        status="running",
        current_stage="requirements",
        state_snapshot={},
        total_tokens=0,
    )
    assert run.project_id == pid
    assert run.status == "running"
    assert run.current_stage == "requirements"
    assert run.total_tokens == 0


def test_stage_execution_model() -> None:
    rid = uuid.uuid4()
    se = StageExecution(pipeline_run_id=rid, stage="design", status="pending", tokens_used=0)
    assert se.stage == "design"
    assert se.tokens_used == 0


def test_artifact_model() -> None:
    rid = uuid.uuid4()
    art = Artifact(
        pipeline_run_id=rid,
        path="src/main.py",
        content_type="text/plain",
        size_bytes=0,
        language="python",
        storage_key="",
    )
    assert art.path == "src/main.py"
    assert art.content_type == "text/plain"
    assert art.language == "python"
