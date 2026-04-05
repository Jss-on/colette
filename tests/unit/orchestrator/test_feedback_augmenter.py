"""Tests for FeedbackAugmenter (Phase 2)."""

from __future__ import annotations

from colette.orchestrator.feedback_augmenter import FeedbackAugmenter
from colette.schemas.rework import ReworkDirective


def _directive(**overrides: object) -> ReworkDirective:
    defaults: dict[str, object] = {
        "source_gate": "design_gate",
        "target_stage": "design",
        "failure_reasons": ["Missing endpoint spec"],
        "attempt_number": 2,
        "max_attempts": 3,
    }
    defaults.update(overrides)
    return ReworkDirective(**defaults)  # type: ignore[arg-type]


class TestFeedbackAugmenter:
    def test_no_directive_returns_base(self) -> None:
        aug = FeedbackAugmenter()
        result = aug.augment_prompt("base prompt", None, None)
        assert result == "base prompt"

    def test_adds_attempt_info(self) -> None:
        aug = FeedbackAugmenter()
        result = aug.augment_prompt("base", _directive(), None)
        assert "attempt 2 of 3" in result
        assert "design_gate" in result

    def test_includes_failure_reasons(self) -> None:
        aug = FeedbackAugmenter()
        directive = _directive(failure_reasons=["Bad schema", "Missing field"])
        result = aug.augment_prompt("base", directive, None)
        assert "Bad schema" in result
        assert "Missing field" in result
        assert "Failure Reasons" in result

    def test_includes_human_feedback(self) -> None:
        aug = FeedbackAugmenter()
        directive = _directive(human_feedback="Add pagination to the API")
        result = aug.augment_prompt("base", directive, None)
        assert "Add pagination to the API" in result
        assert "Human Feedback" in result

    def test_includes_modifications(self) -> None:
        aug = FeedbackAugmenter()
        directive = _directive(modifications={"endpoint": "/api/v2/users"})
        result = aug.augment_prompt("base", directive, None)
        assert "/api/v2/users" in result
        assert "Requested Modifications" in result

    def test_includes_previous_output(self) -> None:
        aug = FeedbackAugmenter()
        prev = {"files": ["a.py", "b.py"], "score": 0.5}
        result = aug.augment_prompt("base", _directive(), prev)
        assert "Previous Attempt Output" in result
        assert "files" in result

    def test_includes_preserved_handoffs(self) -> None:
        aug = FeedbackAugmenter()
        directive = _directive(preserved_handoffs={"requirements": {"user_stories": []}})
        result = aug.augment_prompt("base", directive, None)
        assert "Preserved Handoffs" in result
        assert "requirements" in result

    def test_ends_with_focus_instruction(self) -> None:
        aug = FeedbackAugmenter()
        result = aug.augment_prompt("base", _directive(), None)
        assert "Focus on addressing the failure reasons" in result

    def test_no_failure_reasons_section_when_empty(self) -> None:
        aug = FeedbackAugmenter()
        directive = _directive(failure_reasons=[])
        result = aug.augment_prompt("base", directive, None)
        assert "Failure Reasons" not in result

    def test_no_human_feedback_section_when_none(self) -> None:
        aug = FeedbackAugmenter()
        directive = _directive(human_feedback=None)
        result = aug.augment_prompt("base", directive, None)
        assert "Human Feedback" not in result

    def test_truncates_long_previous_output(self) -> None:
        aug = FeedbackAugmenter()
        long_val = "x" * 1000
        prev = {"data": long_val}
        result = aug.augment_prompt("base", _directive(), prev)
        # Value should be truncated to 500 chars
        assert len(result) < len(long_val) + 500
