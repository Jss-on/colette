"""Tests for rework schemas (Phase 1)."""

from __future__ import annotations

import pytest

from colette.schemas.rework import ReworkDecision, ReworkDirective


class TestReworkDecision:
    """Test ReworkDecision enum."""

    def test_values(self) -> None:
        assert ReworkDecision.PASS == "pass"
        assert ReworkDecision.REWORK_SELF == "rework_self"
        assert ReworkDecision.REWORK_TARGET == "rework_target"

    def test_is_strenum(self) -> None:
        assert isinstance(ReworkDecision.PASS, str)


class TestReworkDirective:
    """Test ReworkDirective model validation, freezing, and defaults."""

    def test_minimal_construction(self) -> None:
        directive = ReworkDirective(
            source_gate="requirements",
            target_stage="requirements",
        )
        assert directive.source_gate == "requirements"
        assert directive.target_stage == "requirements"
        assert directive.failure_reasons == []
        assert directive.human_feedback is None
        assert directive.modifications == {}
        assert directive.attempt_number == 1
        assert directive.max_attempts == 3
        assert directive.preserved_handoffs == {}

    def test_full_construction(self) -> None:
        directive = ReworkDirective(
            source_gate="design",
            target_stage="requirements",
            failure_reasons=["Missing requirement for auth"],
            human_feedback="Add OAuth support",
            modifications={"auth": "add OAuth2"},
            attempt_number=2,
            max_attempts=5,
            preserved_handoffs={"requirements": {"score": 0.9}},
        )
        assert directive.source_gate == "design"
        assert directive.target_stage == "requirements"
        assert len(directive.failure_reasons) == 1
        assert directive.human_feedback == "Add OAuth support"
        assert directive.attempt_number == 2
        assert directive.max_attempts == 5

    def test_frozen(self) -> None:
        directive = ReworkDirective(
            source_gate="testing",
            target_stage="implementation",
        )
        with pytest.raises(Exception):  # noqa: B017, PT011
            directive.source_gate = "other"  # type: ignore[misc]

    def test_attempt_number_ge_1(self) -> None:
        with pytest.raises(Exception):  # noqa: B017, PT011
            ReworkDirective(
                source_gate="x",
                target_stage="y",
                attempt_number=0,
            )

    def test_serialization_roundtrip(self) -> None:
        directive = ReworkDirective(
            source_gate="implementation",
            target_stage="design",
            failure_reasons=["Schema mismatch"],
        )
        data = directive.model_dump(mode="json")
        restored = ReworkDirective.model_validate(data)
        assert restored == directive

    def test_exported_from_schemas_package(self) -> None:
        from colette import schemas

        assert schemas.ReworkDecision.PASS == "pass"
        assert schemas.ReworkDirective is not None
