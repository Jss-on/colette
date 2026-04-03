"""Rework loop schemas for ternary gate routing (Phase 1)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReworkDecision(StrEnum):
    """Ternary gate outcome: pass, rework the failing stage, or rework an upstream stage."""

    PASS = "pass"  # noqa: S105
    REWORK_SELF = "rework_self"
    REWORK_TARGET = "rework_target"


class ReworkDirective(BaseModel):
    """Immutable directive issued when a gate triggers rework."""

    model_config = ConfigDict(frozen=True)

    source_gate: str = Field(description="Which gate triggered the rework.")
    target_stage: str = Field(description="Stage to re-run.")
    failure_reasons: list[str] = Field(
        default_factory=list,
        description="Reasons from QualityGateResult.",
    )
    human_feedback: str | None = Field(
        default=None,
        description="Optional human feedback to inject into rework.",
    )
    modifications: dict[str, str] = Field(
        default_factory=dict,
        description="Structured changes requested by the gate or human.",
    )
    attempt_number: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=3, ge=1)
    preserved_handoffs: dict[str, dict[str, object]] = Field(
        default_factory=dict,
        description="Valid prior handoffs to keep across rework.",
    )
