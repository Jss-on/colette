"""Tests for conversation history manager (FR-MEM-010)."""

from __future__ import annotations

import pytest

from colette.memory.context.history_manager import HistoryManager


class TestHistoryManager:
    def _make(self, **overrides: object) -> HistoryManager:
        defaults: dict[str, object] = {"recent_count": 10}
        defaults.update(overrides)
        return HistoryManager(**defaults)  # type: ignore[arg-type]

    def test_initial_state(self) -> None:
        hm = self._make()
        assert hm.message_count == 0
        assert hm.total_tokens == 0
        assert hm.get_messages() == []

    def test_add_message_returns_new_instance(self) -> None:
        original = self._make()
        updated = original.add_message({"role": "user", "content": "hello"})
        assert original.message_count == 0
        assert updated.message_count == 1

    def test_add_multiple_messages(self) -> None:
        hm = self._make()
        for i in range(5):
            hm = hm.add_message({"role": "user", "content": f"msg {i}"})
        assert hm.message_count == 5

    def test_get_messages_returns_all_when_under_limit(self) -> None:
        hm = self._make(recent_count=10)
        for i in range(5):
            hm = hm.add_message({"role": "user", "content": f"msg {i}"})
        msgs = hm.get_messages()
        assert len(msgs) == 5

    def test_get_messages_includes_summary(self) -> None:
        hm = HistoryManager(
            messages=({"role": "user", "content": "recent"},),
            recent_count=10,
            compacted_summary="prior context here",
        )
        msgs = hm.get_messages()
        assert len(msgs) == 2
        assert "prior context" in msgs[0]["content"]

    def test_needs_summarization(self) -> None:
        hm = self._make()
        # Add messages with substantial content
        for _i in range(20):
            hm = hm.add_message({"role": "user", "content": "x " * 200})
        # With ~1000 tokens of content, budget of 1000 should trigger
        assert hm.needs_summarization(history_budget_tokens=1000) is True

    def test_no_summarization_needed_small_history(self) -> None:
        hm = self._make()
        hm = hm.add_message({"role": "user", "content": "short"})
        assert hm.needs_summarization(history_budget_tokens=10000) is False

    def test_summarize_compacts_older(self) -> None:
        hm = self._make(recent_count=5)
        for i in range(15):
            hm = hm.add_message({"role": "user", "content": f"message {i} " + "a " * 30})

        summarized = hm.summarize(target_tokens=200)
        assert summarized.message_count == 5  # only recent kept
        assert summarized.compacted_summary != ""

    def test_summarize_noop_when_under_limit(self) -> None:
        hm = self._make(recent_count=10)
        for i in range(5):
            hm = hm.add_message({"role": "user", "content": f"msg {i}"})
        summarized = hm.summarize(target_tokens=1000)
        assert summarized.message_count == 5
        assert summarized.compacted_summary == ""

    def test_summarize_appends_to_existing_summary(self) -> None:
        hm = HistoryManager(
            messages=tuple(
                {"role": "user", "content": f"msg {i} " + "a " * 30} for i in range(15)
            ),
            recent_count=5,
            compacted_summary="previous summary",
        )
        summarized = hm.summarize(target_tokens=200)
        assert "previous summary" in summarized.compacted_summary

    def test_immutability(self) -> None:
        hm = self._make()
        with pytest.raises(AttributeError):
            hm.recent_count = 5  # type: ignore[misc]

    def test_total_tokens_includes_summary(self) -> None:
        hm = HistoryManager(
            messages=({"role": "user", "content": "hello world"},),
            recent_count=10,
            compacted_summary="some summary text here",
        )
        assert hm.total_tokens > 0
