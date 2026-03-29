"""Token counting utilities (FR-MEM-004, NFR-OBS-002).

Uses a simple character-based heuristic (~4 chars per token) for budget
enforcement.  Actual usage is tracked via LangChain's `usage_metadata`
after each LLM call, so the heuristic is only used for pre-call checks.
"""

from __future__ import annotations

import json
from typing import Any

# Average characters per token across major providers.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate the token count of a plain text string."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_tokens_for_messages(messages: list[dict[str, Any]]) -> int:
    """Estimate tokens for a list of LangChain-style message dicts.

    Each message is serialized to JSON and counted.  This over-estimates
    slightly (includes JSON keys) which is a safe direction for budget
    enforcement.
    """
    total = 0
    for msg in messages:
        total += estimate_tokens(json.dumps(msg, default=str))
    return total


def check_budget(
    current_tokens: int,
    budget_tokens: int,
    *,
    compaction_threshold: float = 0.70,
) -> tuple[bool, bool]:
    """Check an agent's token usage against its budget.

    Returns:
        (within_budget, needs_compaction):
            within_budget is False if current_tokens >= budget_tokens.
            needs_compaction is True if current_tokens >= compaction_threshold * budget.
    """
    needs_compaction = current_tokens >= (compaction_threshold * budget_tokens)
    within_budget = current_tokens < budget_tokens
    return within_budget, needs_compaction
