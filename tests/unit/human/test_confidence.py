"""Tests for confidence scoring."""

from __future__ import annotations

import pytest

from colette.config import Settings
from colette.human.confidence import evaluate_confidence, extract_confidence_from_response


@pytest.fixture
def settings() -> Settings:
    return Settings()


class TestEvaluateConfidence:
    def test_escalate_below_threshold(self, settings: Settings) -> None:
        result = evaluate_confidence(0.40, settings)
        assert result.action == "escalate"

    def test_flag_between_thresholds(self, settings: Settings) -> None:
        result = evaluate_confidence(0.70, settings)
        assert result.action == "flag_for_review"

    def test_auto_approve_above_threshold(self, settings: Settings) -> None:
        result = evaluate_confidence(0.90, settings)
        assert result.action == "auto_approve"

    def test_boundary_at_escalation_threshold(self, settings: Settings) -> None:
        # Exactly 0.60 should NOT escalate
        result = evaluate_confidence(0.60, settings)
        assert result.action == "flag_for_review"

    def test_boundary_at_flag_threshold(self, settings: Settings) -> None:
        # Exactly 0.85 should auto-approve
        result = evaluate_confidence(0.85, settings)
        assert result.action == "auto_approve"


class TestExtractConfidence:
    def test_extracts_confidence_field(self) -> None:
        assert extract_confidence_from_response({"confidence": 0.8}) == 0.8

    def test_extracts_confidence_score_field(self) -> None:
        assert extract_confidence_from_response({"confidence_score": 0.7}) == 0.7

    def test_missing_defaults_to_050(self) -> None:
        assert extract_confidence_from_response({}) == 0.50

    def test_none_defaults_to_050(self) -> None:
        assert extract_confidence_from_response({"confidence": None}) == 0.50

    def test_string_parsed(self) -> None:
        assert extract_confidence_from_response({"confidence": "0.9"}) == 0.9

    def test_clamps_above_1(self) -> None:
        assert extract_confidence_from_response({"confidence": 1.5}) == 1.0

    def test_clamps_below_0(self) -> None:
        assert extract_confidence_from_response({"confidence": -0.5}) == 0.0
