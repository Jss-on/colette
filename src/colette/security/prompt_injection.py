"""Multi-layer prompt injection defense (NFR-SEC-001).

Detects and strips known injection markers such as system prompt overrides,
role-play attacks, and delimiter injection attempts.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Pattern registry
# Each entry is (pattern_name, regex_pattern).  Patterns are compiled once at
# module level and reused across calls.
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "ignore_previous",
        r"(?i)ignore\s+(all\s+)?previous\s+instructions",
    ),
    (
        "forget_instructions",
        r"(?i)forget\s+(all\s+)?(your\s+)?instructions",
    ),
    (
        "you_are_now",
        r"(?i)you\s+are\s+now\b",
    ),
    (
        "system_prompt_override",
        r"(?i)^system\s*:",
    ),
    (
        "new_instructions_header",
        r"(?i)###\s*NEW\s+INSTRUCTIONS",
    ),
    (
        "act_as",
        r"(?i)act\s+as\s+(a\s+|an\s+)?",
    ),
    (
        "delimiter_backtick_fence",
        r"```\s*(system|instructions?|prompt)",
    ),
    (
        "delimiter_dash_separator",
        r"^-{3,}\s*(system|instructions?|prompt)",
    ),
    (
        "do_anything_now",
        r"(?i)\bDAN\b.*\bdo\s+anything\s+now\b",
    ),
    (
        "jailbreak_keyword",
        r"(?i)\bjailbreak\b",
    ),
    (
        "override_safety",
        r"(?i)override\s+(safety|guardrails?|filters?)",
    ),
    (
        "developer_mode",
        r"(?i)developer\s+mode\s+(enabled|activated|on)",
    ),
)

_COMPILED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.MULTILINE)) for name, pattern in INJECTION_PATTERNS
)

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class InjectionResult(BaseModel):
    """Result of prompt-injection detection analysis."""

    model_config = {"frozen": True}

    detected: bool = Field(description="Whether an injection attempt was detected.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 (none) to 1.0 (certain).",
    )
    patterns_matched: list[str] = Field(
        default_factory=list,
        description="Names of matched injection patterns.",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_injection(text: str) -> InjectionResult:
    """Scan *text* for known prompt-injection patterns.

    Returns an ``InjectionResult`` with matched pattern names and a
    confidence score proportional to the number of distinct patterns found.
    """
    matched: list[str] = []
    for name, regex in _COMPILED_PATTERNS:
        if regex.search(text):
            matched.append(name)

    total = len(_COMPILED_PATTERNS)
    confidence = min(len(matched) / max(total * 0.25, 1), 1.0) if matched else 0.0

    return InjectionResult(
        detected=len(matched) > 0,
        confidence=round(confidence, 4),
        patterns_matched=matched,
    )


def sanitize_input(text: str) -> str:
    """Strip known injection markers from *text*.

    Returns the sanitized string with matched pattern content removed.
    """
    sanitized = text
    for _name, regex in _COMPILED_PATTERNS:
        sanitized = regex.sub("", sanitized)

    # Collapse multiple blank lines left after removals.
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    return sanitized.strip()
