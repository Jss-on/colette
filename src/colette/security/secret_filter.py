"""Secret leak prevention for context, logs, and handoffs (NFR-SEC-002).

Scans text for common secret formats (API keys, tokens, PEM keys, high-entropy
strings) and redacts them before they propagate through the agent pipeline.
"""

from __future__ import annotations

import math
import re

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Pattern registry
# Each entry is (pattern_name, regex_pattern).
# ---------------------------------------------------------------------------

SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    # OpenAI / Anthropic style keys
    (
        "openai_api_key",
        r"sk-[A-Za-z0-9_-]{20,}",
    ),
    # AWS access key IDs
    (
        "aws_access_key",
        r"AKIA[0-9A-Z]{16}",
    ),
    # GitHub personal access tokens (classic + fine-grained)
    (
        "github_token",
        r"gh[pousr]_[A-Za-z0-9_]{36,}",
    ),
    # Generic Bearer tokens in header-style text
    (
        "bearer_token",
        r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*",
    ),
    # Passwords embedded in URIs  (proto://user:PASSWORD@host)
    (
        "password_in_url",
        r"://[^:/?#]+:([^@/?#]+)@",
    ),
    # PEM private keys
    (
        "pem_private_key",
        r"-----BEGIN\s+(RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----",
    ),
    # Stripe keys
    (
        "stripe_key",
        r"(?:sk|pk|rk)_(test|live)_[A-Za-z0-9]{24,}",
    ),
    # Slack tokens / webhooks
    (
        "slack_token",
        r"xox[bprs]-[A-Za-z0-9\-]{10,}",
    ),
    # Base64-encoded blobs >= 40 chars (likely secrets)
    (
        "base64_secret",
        r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{40,}={0,3}(?![A-Za-z0-9+/=])",
    ),
)

_COMPILED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern)) for name, pattern in SECRET_PATTERNS
)

# Entropy threshold for the generic high-entropy detector.
_ENTROPY_THRESHOLD = 4.5
_MIN_HIGH_ENTROPY_LEN = 20

# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class SecretMatch(BaseModel):
    """Describes one detected secret occurrence."""

    model_config = {"frozen": True}

    pattern_name: str = Field(description="Name of the pattern that matched.")
    start: int = Field(description="Start index in the scanned text.")
    end: int = Field(description="End index in the scanned text.")
    redacted_preview: str = Field(
        description="First 4 chars of the matched value followed by '***'.",
    )


class SecretLeakError(ValueError):
    """Raised when secrets are found in text that must be secret-free."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _shannon_entropy(text: str) -> float:
    """Compute Shannon entropy of *text* in bits per character."""
    if not text:
        return 0.0
    length = len(text)
    freq: dict[str, int] = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _high_entropy_matches(text: str) -> list[SecretMatch]:
    """Find contiguous high-entropy substrings that look like secrets."""
    token_re = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")
    matches: list[SecretMatch] = []
    for m in token_re.finditer(text):
        candidate = m.group()
        is_long_enough = len(candidate) >= _MIN_HIGH_ENTROPY_LEN
        is_high_entropy = _shannon_entropy(candidate) >= _ENTROPY_THRESHOLD
        if is_long_enough and is_high_entropy:
            matches.append(
                SecretMatch(
                    pattern_name="high_entropy_string",
                    start=m.start(),
                    end=m.end(),
                    redacted_preview=candidate[:4] + "***",
                )
            )
    return matches


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_for_secrets(text: str) -> list[SecretMatch]:
    """Scan *text* for known secret patterns and high-entropy strings.

    Returns a list of ``SecretMatch`` objects describing each finding.
    """
    results: list[SecretMatch] = []
    seen_ranges: set[tuple[int, int]] = set()

    for name, regex in _COMPILED_PATTERNS:
        for m in regex.finditer(text):
            span = (m.start(), m.end())
            if span not in seen_ranges:
                seen_ranges.add(span)
                matched = m.group()
                results.append(
                    SecretMatch(
                        pattern_name=name,
                        start=m.start(),
                        end=m.end(),
                        redacted_preview=matched[:4] + "***",
                    )
                )

    # High-entropy fallback (avoids double-reporting ranges already found).
    for match in _high_entropy_matches(text):
        span = (match.start, match.end)
        overlaps = any(not (span[1] <= s[0] or span[0] >= s[1]) for s in seen_ranges)
        if not overlaps:
            seen_ranges.add(span)
            results.append(match)

    return sorted(results, key=lambda m: m.start)


def redact_secrets(text: str) -> str:
    """Replace detected secrets with ``[REDACTED:{pattern_name}]``."""
    matches = scan_for_secrets(text)
    if not matches:
        return text

    # Process from end to start so indices stay valid.
    parts = list(text)
    for match in sorted(matches, key=lambda m: m.start, reverse=True):
        replacement = f"[REDACTED:{match.pattern_name}]"
        parts[match.start : match.end] = list(replacement)

    return "".join(parts)


def validate_no_secrets(text: str) -> None:
    """Raise ``SecretLeakError`` if *text* contains any detected secrets.

    Intended as a gate before writing to logs, handoffs, or LLM context.
    """
    matches = scan_for_secrets(text)
    if matches:
        names = ", ".join(m.pattern_name for m in matches)
        msg = f"Secret leak detected ({len(matches)} match(es)): {names}"
        raise SecretLeakError(msg)
