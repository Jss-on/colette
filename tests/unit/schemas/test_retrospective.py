"""Tests for retrospective schema (Phase 6)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from colette.schemas.retrospective import SprintRetrospective


class TestSprintRetrospective:
    def test_minimal(self) -> None:
        retro = SprintRetrospective(sprint_id="S-1")
        assert retro.sprint_id == "S-1"
        assert retro.total_rework_cycles == 0
        assert retro.improvements == []

    def test_full(self) -> None:
        retro = SprintRetrospective(
            sprint_id="S-2",
            total_rework_cycles=3,
            rework_by_stage={"implementation": 2, "design": 1},
            total_tokens_used=50000,
            tokens_by_stage={"implementation": 30000, "design": 20000},
            gate_scores={"impl_gate": 0.75, "design_gate": 0.90},
            human_overrides=1,
            scope_changes=["Added auth requirement"],
            improvements=["Improve design prompts"],
            config_adjustments={"impl_threshold": 0.70},
        )
        assert retro.total_rework_cycles == 3
        assert retro.rework_by_stage["implementation"] == 2
        assert len(retro.improvements) == 1

    def test_frozen(self) -> None:
        retro = SprintRetrospective(sprint_id="S-1")
        with pytest.raises(ValidationError):
            retro.sprint_id = "S-2"  # type: ignore[misc]

    def test_serialization_roundtrip(self) -> None:
        retro = SprintRetrospective(
            sprint_id="S-1",
            total_rework_cycles=1,
            improvements=["Better prompts"],
        )
        data = retro.model_dump()
        restored = SprintRetrospective.model_validate(data)
        assert restored == retro
