"""API request/response Pydantic models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel, frozen=True):
    code: str
    message: str


class ErrorResponse(BaseModel, frozen=True):
    data: None = None
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel, frozen=True):
    """Request body for creating a project."""

    name: str = "Untitled"
    description: str = ""
    user_request: str = Field(..., max_length=32_000)


class ProjectResponse(BaseModel, frozen=True):
    id: uuid.UUID
    name: str
    description: str
    user_request: str
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel, frozen=True):
    data: list[ProjectResponse]
    total: int
    offset: int
    limit: int


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PipelineStatusResponse(BaseModel, frozen=True):
    id: uuid.UUID
    project_id: uuid.UUID
    thread_id: str
    status: str
    current_stage: str
    total_tokens: int
    started_at: datetime
    completed_at: datetime | None
    state_snapshot: dict[str, Any] = Field(default_factory=dict)


class PipelineSSEEvent(BaseModel, frozen=True):
    """SSE event payload for real-time pipeline progress stream."""

    event_type: str
    project_id: str
    stage: str = ""
    agent: str = ""
    model: str = ""
    message: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    elapsed_seconds: float = 0.0
    tokens_used: int = 0
    agent_state: str = ""
    target_agent: str = ""


class PipelineResumeRequest(BaseModel, frozen=True):
    update_values: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class ApprovalResponse(BaseModel, frozen=True):
    id: uuid.UUID
    pipeline_run_id: uuid.UUID
    request_id: str
    stage: str
    tier: str
    status: str
    context_summary: str
    proposed_action: str
    risk_assessment: str
    reviewer_id: str
    comments: str
    created_at: datetime
    decided_at: datetime | None


class ApproveRequest(BaseModel, frozen=True):
    reviewer_id: str = "cli-user"
    modifications: dict[str, Any] = Field(default_factory=dict)
    comments: str = ""


class RejectRequest(BaseModel, frozen=True):
    reviewer_id: str = "cli-user"
    reason: str = ""


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


class ArtifactResponse(BaseModel, frozen=True):
    id: uuid.UUID
    path: str
    content_type: str
    size_bytes: int
    language: str
    created_at: datetime


class ArtifactListResponse(BaseModel, frozen=True):
    data: list[ArtifactResponse]
    total: int


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthCheck(BaseModel, frozen=True):
    name: str
    status: str  # "ok" | "degraded" | "unhealthy"
    latency_ms: float | None = None


class HealthResponse(BaseModel, frozen=True):
    status: str  # "healthy" | "degraded" | "unhealthy"
    version: str
    checks: list[HealthCheck] = Field(default_factory=list)
