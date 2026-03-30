"""Initial schema for Colette Phase 8.

Revision ID: 001
Revises: None
Create Date: 2026-03-30
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(255), unique=True, nullable=False),
        sa.Column("api_key_hash", sa.String(128), nullable=False, server_default=""),
        sa.Column("role", sa.String(50), nullable=False, server_default="observer"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, server_default="Untitled"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("user_request", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="created"),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("thread_id", sa.String(255), unique=True, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column(
            "current_stage", sa.String(50), nullable=False, server_default="requirements"
        ),
        sa.Column("state_snapshot", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_tokens", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pipeline_runs_project_id", "pipeline_runs", ["project_id"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])

    op.create_table(
        "stage_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("gate_result", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tokens_used", sa.Integer, server_default="0"),
    )
    op.create_index(
        "ix_stage_executions_pipeline_run_id", "stage_executions", ["pipeline_run_id"]
    )

    op.create_table(
        "approval_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(255), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("reviewer_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("context_summary", sa.Text, nullable=False, server_default=""),
        sa.Column("proposed_action", sa.Text, nullable=False, server_default=""),
        sa.Column("risk_assessment", sa.Text, nullable=False, server_default=""),
        sa.Column("modifications", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("comments", sa.Text, nullable=False, server_default=""),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_approval_records_pipeline_run_id", "approval_records", ["pipeline_run_id"]
    )
    op.create_index("ix_approval_records_status", "approval_records", ["status"])

    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id"),
            nullable=False,
        ),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False, server_default="text/plain"),
        sa.Column("size_bytes", sa.Integer, server_default="0"),
        sa.Column("storage_key", sa.String(1024), nullable=False, server_default=""),
        sa.Column("language", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_artifacts_pipeline_run_id", "artifacts", ["pipeline_run_id"])


def downgrade() -> None:
    op.drop_table("artifacts")
    op.drop_table("approval_records")
    op.drop_table("stage_executions")
    op.drop_table("pipeline_runs")
    op.drop_table("projects")
    op.drop_table("users")
