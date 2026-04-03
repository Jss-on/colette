"""Anthropic prompt caching support (cost optimization).

Wraps system messages with ``cache_control`` metadata so that
identical system prompts (including JSON schemas) are cached by
the Anthropic API.  Cached reads cost 0.1x normal input tokens.

LiteLLM passes the content-block format through to Anthropic's
API directly, including the ``cache_control`` field.
"""

from __future__ import annotations

import structlog
from langchain_core.messages import SystemMessage

logger = structlog.get_logger(__name__)

# Anthropic requires at least 1024 tokens (~4096 chars) for caching.
_MIN_CACHEABLE_CHARS = 4096


def build_cached_system_message(prompt: str) -> SystemMessage:
    """Build a SystemMessage with Anthropic cache_control if eligible.

    Uses content-block format so LiteLLM passes ``cache_control``
    through to the Anthropic API.  Falls back to a plain SystemMessage
    for prompts that are too short to cache.
    """
    if len(prompt) < _MIN_CACHEABLE_CHARS:
        return SystemMessage(content=prompt)

    return SystemMessage(
        content=[
            {
                "type": "text",
                "text": prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    )


def extract_cache_tokens(usage: dict[str, int]) -> tuple[int, int]:
    """Extract cache hit/miss tokens from LLM usage metadata.

    Returns:
        (cache_read_tokens, cache_creation_tokens)
    """
    return (
        usage.get("cache_read_input_tokens", 0),
        usage.get("cache_creation_input_tokens", 0),
    )
