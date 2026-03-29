"""Tests for context budget tracker (FR-MEM-004)."""

from __future__ import annotations

import pytest

from colette.memory.context.budget_tracker import ContextBudgetTracker
from colette.memory.exceptions import BudgetExceededError


class TestContextBudgetTracker:
    def _make(self, **overrides: object) -> ContextBudgetTracker:
        defaults: dict[str, object] = {
            "agent_role": "test_agent",
            "total_budget": 100_000,
        }
        defaults.update(overrides)
        return ContextBudgetTracker(**defaults)  # type: ignore[arg-type]

    def test_initial_state(self) -> None:
        tracker = self._make()
        assert tracker.total_used == 0
        assert tracker.utilization == 0.0
        assert tracker.needs_compaction() is False

    def test_slot_budget_calculation(self) -> None:
        tracker = self._make(total_budget=100_000)
        assert tracker.slot_budget("system_prompt") == 10_000  # 10%
        assert tracker.slot_budget("tools") == 15_000  # 15%
        assert tracker.slot_budget("retrieved_context") == 35_000  # 35%
        assert tracker.slot_budget("history") == 15_000  # 15%
        assert tracker.slot_budget("output") == 25_000  # 25%

    def test_record_usage_returns_new_instance(self) -> None:
        original = self._make()
        updated = original.record_usage("history", 5000)
        assert original.total_used == 0
        assert updated.total_used == 5000

    def test_record_usage_accumulates(self) -> None:
        tracker = self._make()
        tracker = tracker.record_usage("history", 3000)
        tracker = tracker.record_usage("history", 2000)
        assert tracker.slot_used("history") == 5000

    def test_record_usage_raises_on_overflow(self) -> None:
        tracker = self._make(total_budget=100_000)
        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.record_usage("history", 16_000)  # limit is 15_000
        assert exc_info.value.slot == "history"
        assert exc_info.value.limit == 15_000

    def test_available_tokens(self) -> None:
        tracker = self._make(total_budget=100_000)
        tracker = tracker.record_usage("history", 5000)
        assert tracker.available_tokens("history") == 10_000

    def test_utilization(self) -> None:
        tracker = self._make(total_budget=100_000)
        tracker = tracker.record_usage("history", 10_000)
        tracker = tracker.record_usage("tools", 10_000)
        assert tracker.utilization == pytest.approx(0.20)

    def test_needs_compaction_at_threshold(self) -> None:
        tracker = self._make(total_budget=100_000)
        tracker = tracker.record_usage("retrieved_context", 35_000)
        tracker = tracker.record_usage("history", 15_000)
        tracker = tracker.record_usage("output", 20_000)
        # 70_000 / 100_000 = 0.70
        assert tracker.needs_compaction(threshold=0.70) is True

    def test_needs_compaction_below_threshold(self) -> None:
        tracker = self._make(total_budget=100_000)
        tracker = tracker.record_usage("history", 5000)
        assert tracker.needs_compaction(threshold=0.70) is False

    def test_to_summary(self) -> None:
        tracker = self._make(total_budget=100_000)
        tracker = tracker.record_usage("history", 5000)
        summary = tracker.to_summary()
        assert summary["agent_role"] == "test_agent"
        assert summary["total_budget"] == 100_000
        assert summary["total_used"] == 5000
        assert "slots" in summary

    def test_zero_budget(self) -> None:
        tracker = self._make(total_budget=0)
        assert tracker.utilization == 0.0

    def test_immutability(self) -> None:
        tracker = self._make()
        with pytest.raises(AttributeError):
            tracker.total_budget = 999  # type: ignore[misc]
