"""Regex-based security scanner with deterministic severity.

Replaces LLM-assigned ``severity`` + ``confidence`` on security findings.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from colette.eval._pattern_registry import SECURITY_PATTERNS, SecurityPattern

# ── Data types ───────────────────────────────────────────────────────


class PatternMatch(NamedTuple):
    pattern_id: str
    category: str
    severity: str
    file_path: str
    line: int
    matched_text: str
    description: str
    recommendation: str


class SecurityScanReport(NamedTuple):
    matches: tuple[PatternMatch, ...]
    has_blocking: bool  # any CRITICAL or HIGH
    patterns_checked: int
    files_scanned: int


# ── Internal helpers ─────────────────────────────────────────────────


def _detect_language(file_path: str) -> str:
    """Infer language from file extension."""
    if file_path.endswith(".py"):
        return "python"
    if file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
        return "typescript"
    return "unknown"


def _match_pattern(
    pattern: SecurityPattern,
    file_path: str,
    content: str,
) -> list[PatternMatch]:
    """Per-line matching with negative pattern suppression."""
    matches: list[PatternMatch] = []
    compiled = re.compile(pattern.pattern, re.IGNORECASE)
    neg_compiled = (
        re.compile(pattern.negative_pattern, re.IGNORECASE) if pattern.negative_pattern else None
    )

    for lineno, line in enumerate(content.splitlines(), 1):
        if compiled.search(line):
            # Check negative pattern for suppression
            if neg_compiled and neg_compiled.search(line):
                continue
            # For auth bypass, also check surrounding context
            if pattern.id == "SEC-AUTH-001" and neg_compiled:
                # Look at preceding lines for auth decorators
                lines = content.splitlines()
                start = max(0, lineno - 4)
                context = "\n".join(lines[start : lineno - 1])
                if neg_compiled.search(context):
                    continue

            matches.append(
                PatternMatch(
                    pattern_id=pattern.id,
                    category=pattern.category,
                    severity=pattern.severity,
                    file_path=file_path,
                    line=lineno,
                    matched_text=line.strip()[:120],
                    description=pattern.description,
                    recommendation=pattern.recommendation,
                )
            )

    return matches


def _consolidate_matches(
    matches: list[PatternMatch],
) -> tuple[PatternMatch, ...]:
    """Deduplicate by (pattern_id, file_path, line)."""
    seen: set[tuple[str, str, int]] = set()
    unique: list[PatternMatch] = []
    for m in matches:
        key = (m.pattern_id, m.file_path, m.line)
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return tuple(unique)


# ── Main entry ───────────────────────────────────────────────────────


def scan_files(
    files: list[dict[str, str]],
) -> SecurityScanReport:
    """Scan files for security anti-patterns."""
    all_matches: list[PatternMatch] = []
    files_scanned = 0

    for f in files:
        file_path = f.get("path", "")
        content = f.get("content", "")
        if not content:
            continue

        lang = _detect_language(file_path)
        files_scanned += 1

        for pattern in SECURITY_PATTERNS:
            if lang in pattern.languages:
                all_matches.extend(_match_pattern(pattern, file_path, content))

    consolidated = _consolidate_matches(all_matches)
    has_blocking = any(m.severity in ("CRITICAL", "HIGH") for m in consolidated)

    return SecurityScanReport(
        matches=consolidated,
        has_blocking=has_blocking,
        patterns_checked=len(SECURITY_PATTERNS),
        files_scanned=files_scanned,
    )
