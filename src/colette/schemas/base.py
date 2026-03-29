"""Base handoff schema that all inter-stage schemas inherit from (FR-ORC-020/021/024)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class HandoffSchema(BaseModel):
    """Base schema for all inter-stage handoff objects.

    Every handoff carries metadata for versioning, audit, and size enforcement.
    """

    schema_version: str = Field(
        description="Semantic version of this schema (FR-ORC-021).",
    )
    project_id: str = Field(description="Unique project identifier.")
    source_stage: str = Field(description="Stage that produced this handoff.")
    target_stage: str = Field(description="Stage that will consume this handoff.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    quality_gate_passed: bool = Field(
        default=False,
        description="Whether the source stage's quality gate passed.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context: user_id, key decisions, error context.",
    )
