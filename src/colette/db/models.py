"""SQLAlchemy ORM models for persistent project/pipeline state."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from colette.db.base import Base
from colette.schemas.common import StageName, StageStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(Base):
    """A Colette user with an assigned RBAC role."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="observer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    projects: Mapped[list[Project]] = relationship(back_populates="owner")


class Project(Base):
    """A user-submitted software project."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_request: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    repo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    repo_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    owner: Mapped[User | None] = relationship(back_populates="projects")
    pipeline_runs: Mapped[list[PipelineRun]] = relationship(
        back_populates="project", order_by="PipelineRun.started_at.desc()"
    )

    __table_args__ = (Index("ix_projects_status", "status"),)


class PipelineRun(Base):
    """A single execution of the 6-stage SDLC pipeline."""

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="requirements")
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # type: ignore[type-arg]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    project: Mapped[Project] = relationship(back_populates="pipeline_runs")
    stage_executions: Mapped[list[StageExecution]] = relationship(back_populates="pipeline_run")
    approval_records: Mapped[list[ApprovalRecord]] = relationship(back_populates="pipeline_run")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="pipeline_run")

    __table_args__ = (
        Index("ix_pipeline_runs_project_id", "project_id"),
        Index("ix_pipeline_runs_status", "status"),
    )


class StageExecution(Base):
    """Tracks execution of a single pipeline stage."""

    __tablename__ = "stage_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False
    )
    stage: Mapped[str] = mapped_column(
        Enum(StageName, name="stage_name", create_constraint=False), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(StageStatus, name="stage_status", create_constraint=False),
        nullable=False,
        default=StageStatus.PENDING.value,
    )
    gate_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[type-arg]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tokens_used: Mapped[int] = mapped_column(default=0)

    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="stage_executions")

    __table_args__ = (Index("ix_stage_executions_pipeline_run_id", "pipeline_run_id"),)


class ApprovalRecord(Base):
    """Persists human approval decisions."""

    __tablename__ = "approval_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    reviewer_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    context_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    proposed_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_assessment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    modifications: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # type: ignore[type-arg]
    comments: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="approval_records")

    __table_args__ = (
        Index("ix_approval_records_pipeline_run_id", "pipeline_run_id"),
        Index("ix_approval_records_status", "status"),
    )


class Artifact(Base):
    """A generated file or bundle produced by a pipeline run."""

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="text/plain")
    size_bytes: Mapped[int] = mapped_column(default=0)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="artifacts")

    __table_args__ = (Index("ix_artifacts_pipeline_run_id", "pipeline_run_id"),)
