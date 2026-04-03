"""Requirements evolution schemas for multi-sprint lifecycle (Phase 4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RequirementAmendment(BaseModel):
    """A single amendment to the base requirements during a sprint."""

    model_config = ConfigDict(frozen=True)

    sprint_id: str
    source: str = Field(
        description="Origin: gate_feedback | human_review | test_discovery | retrospective",
    )
    added_stories: list[dict[str, object]] = Field(default_factory=list)
    modified_stories: list[tuple[str, dict[str, object]]] = Field(default_factory=list)
    removed_story_ids: list[str] = Field(default_factory=list)
    added_nfrs: list[dict[str, object]] = Field(default_factory=list)
    rationale: str = ""


class EvolvingRequirements(BaseModel):
    """Requirements that accumulate amendments across sprints."""

    model_config = ConfigDict(frozen=True)

    base_requirements: dict[str, object] = Field(default_factory=dict)
    amendments: list[RequirementAmendment] = Field(default_factory=list)
