"""Token counting utilities (FR-MEM-004, NFR-OBS-002).

Uses a simple character-based heuristic (~4 chars per token) for budget
enforcement.  Actual usage is tracked via LangChain's `usage_metadata`
after each LLM call, so the heuristic is only used for pre-call checks.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Average characters per token across major providers.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate the token count of a plain text string.

    Uses a heuristic of ~4 characters per token.  Actual usage is
    tracked via LangChain's ``usage_metadata`` after each LLM call.

    Args:
        text: The string to estimate.

    Returns:
        Estimated token count (minimum 1).
    """
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_tokens_for_messages(messages: list[dict[str, Any]]) -> int:
    """Estimate tokens for a list of LangChain-style message dicts.

    Each message is serialized to JSON and counted.  This over-estimates
    slightly (includes JSON keys) which is a safe direction for budget
    enforcement.

    Args:
        messages: List of message dicts with ``role`` and ``content`` keys.

    Returns:
        Estimated total token count across all messages.
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

    Args:
        current_tokens: Current token count for the agent.
        budget_tokens: Maximum token budget for the agent.
        compaction_threshold: Fraction of budget that triggers compaction
            (default 0.70, i.e. 70%).

    Returns:
        A tuple of ``(within_budget, needs_compaction)``:

        - *within_budget* is ``False`` if *current_tokens* >= *budget_tokens*.
        - *needs_compaction* is ``True`` if usage exceeds the threshold.
    """
    needs_compaction = current_tokens >= (compaction_threshold * budget_tokens)
    within_budget = current_tokens < budget_tokens

    if not within_budget:
        logger.warning(
            "token_budget_exceeded",
            current=current_tokens,
            budget=budget_tokens,
        )
    elif needs_compaction:
        logger.info(
            "token_compaction_recommended",
            current=current_tokens,
            budget=budget_tokens,
            threshold=compaction_threshold,
            utilization=round(current_tokens / budget_tokens, 2),
        )

    return within_budget, needs_compaction
