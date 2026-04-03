"""Base handoff schema that all inter-stage schemas inherit from (FR-ORC-020/021/024)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

# Default max handoff size in characters (proxy for ~32K tokens at ~4 chars/token).
# Design handoffs carry OpenAPI specs + architecture + DB schema; 32K was too tight.
DEFAULT_MAX_HANDOFF_CHARS = 128_000


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

    # ── Size enforcement (FR-ORC-024) ────────────────────────────────

    @model_validator(mode="after")
    def _enforce_size_limit(self) -> Self:
        size = len(self.model_dump_json())
        if size > DEFAULT_MAX_HANDOFF_CHARS:
            msg = (
                f"Handoff exceeds size limit: {size} chars "
                f"(max {DEFAULT_MAX_HANDOFF_CHARS}). "
                "Compress content or use references."
            )
            raise ValueError(msg)
        return self

    # ── Version compatibility (FR-ORC-021) ───────────────────────────

    def check_version_compatible(self, expected: str) -> None:
        """Reject if the major version doesn't match *expected*.

        Raises ValueError on mismatch so the receiving stage can
        return a structured error instead of crashing.
        """
        actual_major = self.schema_version.split(".")[0]
        expected_major = expected.split(".")[0]
        if actual_major != expected_major:
            msg = (
                f"Schema version mismatch: got {self.schema_version}, "
                f"expected major version {expected_major}.x"
            )
            raise ValueError(msg)

    # ── Serialization helpers ────────────────────────────────────────

    def estimated_tokens(self) -> int:
        """Rough token estimate (~4 chars per token)."""
        return len(self.model_dump_json()) // 4

    def to_json(self) -> str:
        """Serialize to a compact JSON string for persistence (FR-ORC-023)."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str | bytes) -> Self:
        """Deserialize from JSON, validating on receipt (FR-ORC-020)."""
        return cls.model_validate_json(data)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict with JSON-safe values."""
        result: dict[str, Any] = json.loads(self.model_dump_json())
        return result
