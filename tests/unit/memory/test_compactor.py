"""Tests for verbatim compactor (FR-MEM-005)."""

from __future__ import annotations

from colette.memory.context.compactor import VerbatimCompactor


class TestVerbatimCompactor:
    def _make(self) -> VerbatimCompactor:
        return VerbatimCompactor()

    def test_no_compaction_when_under_target(self) -> None:
        compactor = self._make()
        result = compactor.compact("short text", target_tokens=1000)
        assert result.compacted_content == "short text"
        assert result.reduction_ratio == 0.0

    def test_compaction_reduces_content(self) -> None:
        compactor = self._make()
        # Build content larger than target
        paragraphs = [f"Paragraph {i}: " + "x " * 100 for i in range(20)]
        content = "\n\n".join(paragraphs)
        result = compactor.compact(content, target_tokens=200)
        assert result.compacted_tokens <= 200
        assert result.reduction_ratio > 0

    def test_preserves_exact_text(self) -> None:
        compactor = self._make()
        content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = compactor.compact(content, target_tokens=10)
        # Each selected segment should be exact text from original
        for segment in result.compacted_content.split("\n\n"):
            if segment.strip():
                assert segment in content

    def test_prefers_code_blocks(self) -> None:
        compactor = self._make()
        content = (
            "Some prose about the system.\n\n"
            "```python\ndef important_func():\n    return 42\n```\n\n"
            "More prose here that is less important."
        )
        result = compactor.compact(content, target_tokens=30)
        assert "def important_func" in result.compacted_content

    def test_empty_content(self) -> None:
        compactor = self._make()
        result = compactor.compact("", target_tokens=100)
        assert result.compacted_content == ""
        assert result.reduction_ratio == 0.0

    def test_compact_messages_no_compaction_needed(self) -> None:
        compactor = self._make()
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(5)]
        result_msgs, result = compactor.compact_messages(messages, target_tokens=1000)
        assert result is None
        assert len(result_msgs) == 5

    def test_compact_messages_compacts_older(self) -> None:
        compactor = self._make()
        messages = [
            {"role": "user", "content": f"message number {i} " + "x " * 50}
            for i in range(15)
        ]
        result_msgs, result = compactor.compact_messages(
            messages, target_tokens=5000, keep_recent=10
        )
        assert result is not None
        # Should have system messages + compacted older + 10 recent
        recent_msgs = [m for m in result_msgs if "Compacted" not in m.get("content", "")]
        assert len(recent_msgs) >= 10

    def test_compact_messages_preserves_system(self) -> None:
        compactor = self._make()
        messages = [
            {"role": "system", "content": "You are helpful."},
            *[{"role": "user", "content": f"msg {i} " + "a " * 50} for i in range(15)],
        ]
        result_msgs, _ = compactor.compact_messages(
            messages, target_tokens=5000, keep_recent=10
        )
        system_msgs = [m for m in result_msgs if m["role"] == "system"]
        assert len(system_msgs) >= 1
        assert any("You are helpful" in m["content"] for m in system_msgs)
