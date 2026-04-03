"""Tests for adaptive configuration tuning (Phase 6)."""

from __future__ import annotations

import pytest

from colette.orchestrator.adaptive_config import adjust_gate_thresholds, adjust_model_tiers
from colette.schemas.retrospective import SprintRetrospective


def _retro(**overrides: object) -> SprintRetrospective:
    defaults: dict[str, object] = {"sprint_id": "S-1"}
    defaults.update(overrides)
    return SprintRetrospective(**defaults)  # type: ignore[arg-type]


class TestAdjustGateThresholds:
    def test_tighten_high_pass_rate(self) -> None:
        retro = _retro(gate_scores={"impl_gate": 0.96})
        result = adjust_gate_thresholds(retro, {"impl_gate": 0.80})
        assert result["impl_gate"] == pytest.approx(0.85)

    def test_loosen_low_pass_rate(self) -> None:
        retro = _retro(gate_scores={"design_gate": 0.55})
        result = adjust_gate_thresholds(retro, {"design_gate": 0.80})
        assert result["design_gate"] == pytest.approx(0.75)

    def test_no_change_moderate_score(self) -> None:
        retro = _retro(gate_scores={"req_gate": 0.80})
        result = adjust_gate_thresholds(retro, {"req_gate": 0.80})
        assert result["req_gate"] == 0.80

    def test_tighten_caps_at_099(self) -> None:
        retro = _retro(gate_scores={"gate": 0.97})
        result = adjust_gate_thresholds(retro, {"gate": 0.97})
        assert result["gate"] <= 0.99

    def test_loosen_floors_at_050(self) -> None:
        retro = _retro(gate_scores={"gate": 0.50})
        result = adjust_gate_thresholds(retro, {"gate": 0.52})
        assert result["gate"] >= 0.50

    def test_default_threshold_when_missing(self) -> None:
        retro = _retro(gate_scores={"new_gate": 0.96})
        result = adjust_gate_thresholds(retro)
        assert result["new_gate"] == pytest.approx(0.85)  # 0.80 default + 0.05

    def test_empty_retrospective(self) -> None:
        retro = _retro()
        result = adjust_gate_thresholds(retro)
        assert result == {}


class TestAdjustModelTiers:
    def test_upgrade_on_high_rework(self) -> None:
        retro = _retro(rework_by_stage={"implementation": 3})
        result = adjust_model_tiers(retro, {"implementation": "execution"})
        assert result["implementation"] == "planning"

    def test_no_upgrade_on_low_rework(self) -> None:
        retro = _retro(rework_by_stage={"implementation": 1})
        result = adjust_model_tiers(retro, {"implementation": "execution"})
        assert result["implementation"] == "execution"

    def test_upgrade_from_validation(self) -> None:
        retro = _retro(rework_by_stage={"testing": 2})
        result = adjust_model_tiers(retro, {"testing": "validation"})
        assert result["testing"] == "execution"

    def test_already_max_tier(self) -> None:
        retro = _retro(rework_by_stage={"design": 5})
        result = adjust_model_tiers(retro, {"design": "planning"})
        assert result["design"] == "planning"

    def test_empty_retrospective(self) -> None:
        retro = _retro()
        result = adjust_model_tiers(retro)
        assert result == {}

    def test_default_tier_when_missing(self) -> None:
        retro = _retro(rework_by_stage={"new_stage": 3})
        result = adjust_model_tiers(retro)
        assert result["new_stage"] == "planning"  # execution -> planning
