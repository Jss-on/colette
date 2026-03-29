"""Conversation history management (FR-MEM-010).

Maintains a sliding window of recent messages with compressed
summaries of older messages.  Immutable — mutations return new instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from colette.llm.token_counter import estimate_tokens
from colette.memory.context.compactor import VerbatimCompactor

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class HistoryManager:
    """Immutable conversation history with sliding-window compaction.

    Keeps *recent_count* most recent messages verbatim.  Older messages
    are compacted via :class:`VerbatimCompactor` when history exceeds
    the budget.
    """

    messages: tuple[dict[str, str], ...] = field(default_factory=tuple)
    recent_count: int = 10
    compacted_summary: str = ""

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def total_tokens(self) -> int:
        total = sum(estimate_tokens(m.get("content", "")) for m in self.messages)
        if self.compacted_summary:
            total += estimate_tokens(self.compacted_summary)
        return total

    def add_message(self, message: dict[str, str]) -> HistoryManager:
        """Append a message. Returns a new instance."""
        return HistoryManager(
            messages=(*self.messages, message),
            recent_count=self.recent_count,
            compacted_summary=self.compacted_summary,
        )

    def get_messages(self) -> list[dict[str, str]]:
        """Return renderable messages: compacted summary + recent messages."""
        result: list[dict[str, str]] = []
        if self.compacted_summary:
            result.append({
                "role": "system",
                "content": f"[Prior conversation summary]\n{self.compacted_summary}",
            })
        recent = self.messages[-self.recent_count:]
        result.extend(recent)
        return result

    def needs_summarization(self, history_budget_tokens: int) -> bool:
        """Whether history exceeds 75% of its budget allocation."""
        return self.total_tokens >= int(history_budget_tokens * 0.75)

    def summarize(self, target_tokens: int) -> HistoryManager:
        """Compact older messages using verbatim extraction.

        Returns a new instance with older messages replaced by a
        compacted summary appended to any existing summary.
        """
        if len(self.messages) <= self.recent_count:
            return self

        recent = self.messages[-self.recent_count:]
        older = self.messages[:-self.recent_count]

        older_text = "\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')}"
            for m in older
        )

        compactor = VerbatimCompactor()
        result = compactor.compact(older_text, target_tokens)

        # Append to existing summary
        new_summary = self.compacted_summary
        if new_summary:
            new_summary += "\n---\n"
        new_summary += result.compacted_content

        logger.info(
            "history_summarized",
            older_messages=len(older),
            kept_recent=len(recent),
            original_tokens=result.original_tokens,
            compacted_tokens=result.compacted_tokens,
        )

        return HistoryManager(
            messages=recent,
            recent_count=self.recent_count,
            compacted_summary=new_summary,
        )
