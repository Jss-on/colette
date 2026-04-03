"""Tests for approval routing logic."""

from __future__ import annotations

import pytest

from colette.config import Settings
from colette.human.approval import (
    apply_modifications,
    create_approval_request,
    determine_approval_action,
)
from colette.orchestrator.state import create_initial_state
from colette.schemas.common import ApprovalTier


@pytest.fixture
def settings() -> Settings:
    return Settings()


class TestDetermineApprovalAction:
    def test_t0_always_interrupts(self, settings: Settings) -> None:
        assert determine_approval_action(ApprovalTier.T0_CRITICAL, 0.99, settings) == "interrupt"

    def test_t1_always_interrupts(self, settings: Settings) -> None:
        assert determine_approval_action(ApprovalTier.T1_HIGH, 0.99, settings) == "interrupt"

    def test_t2_interrupts_low_confidence(self, settings: Settings) -> None:
        assert determine_approval_action(ApprovalTier.T2_MODERATE, 0.50, settings) == "interrupt"

    def test_t2_interrupts_none_confidence(self, settings: Settings) -> None:
        assert determine_approval_action(ApprovalTier.T2_MODERATE, None, settings) == "interrupt"

    def test_t2_auto_approves_high_confidence(self, settings: Settings) -> None:
        result = determine_approval_action(ApprovalTier.T2_MODERATE, 0.90, settings)
        assert result == "auto_approve"

    def test_t3_always_auto_approves(self, settings: Settings) -> None:
        assert determine_approval_action(ApprovalTier.T3_ROUTINE, 0.10, settings) == "auto_approve"


class TestCreateApprovalRequest:
    def test_builds_request(self, settings: Settings) -> None:
        state = dict(create_initial_state("proj-1"))
        req = create_approval_request(
            state,
            ApprovalTier.T0_CRITICAL,
            "Deploy to prod",
            "Run deployment",
            settings=settings,
        )
        assert req.project_id == "proj-1"
        assert req.tier == ApprovalTier.T0_CRITICAL
        assert req.sla_deadline is not None

    def test_t3_has_no_sla(self, settings: Settings) -> None:
        state = dict(create_initial_state("proj-1"))
        req = create_approval_request(
            state,
            ApprovalTier.T3_ROUTINE,
            "Lint",
            "Auto-format",
            settings=settings,
        )
        assert req.sla_deadline is None


class TestApplyModifications:
    def test_merges_without_mutation(self) -> None:
        original = {"a": 1, "b": 2}
        result = apply_modifications(original, {"b": 99, "c": 3})
        assert result == {"a": 1, "b": 99, "c": 3}
        assert original == {"a": 1, "b": 2}

    def test_empty_modifications_returns_original(self) -> None:
        original = {"a": 1}
        result = apply_modifications(original, {})
        assert result is original

    def test_emits_feedback_applied_event(self) -> None:
        from unittest.mock import MagicMock

        from colette.orchestrator.event_bus import EventType, event_bus_var

        bus = MagicMock()
        token = event_bus_var.set(bus)
        try:
            apply_modifications({"a": 1}, {"b": 2})
            bus.emit.assert_called_once()
            event = bus.emit.call_args[0][0]
            assert event.event_type == EventType.FEEDBACK_APPLIED
        finally:
            event_bus_var.reset(token)
