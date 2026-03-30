"""Tests for API request/response schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from colette.api.schemas import (
    ArtifactListResponse,
    ArtifactResponse,
    ErrorDetail,
    ErrorResponse,
    HealthCheck,
    HealthResponse,
    ProjectCreate,
    ProjectResponse,
)


def test_project_create_valid() -> None:
    body = ProjectCreate(user_request="Build a TODO app")
    assert body.user_request == "Build a TODO app"
    assert body.name == "Untitled"


def test_project_create_too_long() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(user_request="x" * 33_000)


def test_project_response() -> None:
    now = datetime.now(UTC)
    resp = ProjectResponse(
        id=uuid.uuid4(),
        name="Test",
        description="desc",
        user_request="req",
        status="created",
        created_at=now,
        updated_at=now,
    )
    assert resp.status == "created"


def test_error_response() -> None:
    err = ErrorResponse(error=ErrorDetail(code="not_found", message="Not found"))
    assert err.data is None
    assert err.error.code == "not_found"


def test_health_check() -> None:
    hc = HealthCheck(name="database", status="ok", latency_ms=1.5)
    assert hc.latency_ms == 1.5


def test_health_response() -> None:
    hr = HealthResponse(status="healthy", version="0.1.0")
    assert hr.checks == []


def test_artifact_list_response() -> None:
    now = datetime.now(UTC)
    resp = ArtifactListResponse(
        data=[
            ArtifactResponse(
                id=uuid.uuid4(),
                path="src/main.py",
                content_type="text/plain",
                size_bytes=100,
                language="python",
                created_at=now,
            )
        ],
        total=1,
    )
    assert resp.total == 1
    assert len(resp.data) == 1
