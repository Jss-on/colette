"""Tests for requirements evolution schemas (Phase 4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from colette.schemas.evolution import EvolvingRequirements, RequirementAmendment


class TestRequirementAmendment:
    def test_minimal(self) -> None:
        amendment = RequirementAmendment(
            sprint_id="SPRINT-1",
            source="gate_feedback",
        )
        assert amendment.sprint_id == "SPRINT-1"
        assert amendment.added_stories == []
        assert amendment.rationale == ""

    def test_full(self) -> None:
        amendment = RequirementAmendment(
            sprint_id="SPRINT-2",
            source="human_review",
            added_stories=[{"title": "New story"}],
            removed_story_ids=["US-001"],
            rationale="Scope change after review",
        )
        assert len(amendment.added_stories) == 1
        assert amendment.removed_story_ids == ["US-001"]

    def test_frozen(self) -> None:
        amendment = RequirementAmendment(sprint_id="S-1", source="test")
        with pytest.raises(ValidationError):
            amendment.source = "new"  # type: ignore[misc]


class TestEvolvingRequirements:
    def test_empty(self) -> None:
        er = EvolvingRequirements()
        assert er.base_requirements == {}
        assert er.amendments == []

    def test_with_amendments(self) -> None:
        amendment = RequirementAmendment(sprint_id="S-1", source="gate_feedback")
        er = EvolvingRequirements(
            base_requirements={"user_stories": []},
            amendments=[amendment],
        )
        assert len(er.amendments) == 1

    def test_frozen(self) -> None:
        er = EvolvingRequirements()
        with pytest.raises(ValidationError):
            er.base_requirements = {}  # type: ignore[misc]

    def test_serialization_roundtrip(self) -> None:
        er = EvolvingRequirements(
            base_requirements={"stories": ["US-001"]},
            amendments=[
                RequirementAmendment(sprint_id="S-1", source="test"),
            ],
        )
        data = er.model_dump()
        restored = EvolvingRequirements.model_validate(data)
        assert restored == er
