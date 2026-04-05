"""Sprint retrospective schema for adaptive learning (Phase 6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SprintRetrospective(BaseModel):
    """Analysis of a completed sprint for adaptive improvement."""

    model_config = ConfigDict(frozen=True)

    sprint_id: str
    total_rework_cycles: int = 0
    rework_by_stage: dict[str, int] = Field(default_factory=dict)
    total_tokens_used: int = 0
    tokens_by_stage: dict[str, int] = Field(default_factory=dict)
    gate_scores: dict[str, float] = Field(default_factory=dict)
    human_overrides: int = 0
    scope_changes: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    config_adjustments: dict[str, object] = Field(default_factory=dict)
