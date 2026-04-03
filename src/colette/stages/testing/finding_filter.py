"""Deterministic post-LLM security finding filter (FR-TST-006).

LLM-based scanners do not reliably follow confidence and consolidation
instructions.  This module provides a safety net: low-confidence findings
are removed and duplicates are merged before the handoff reaches the gate.
"""

from __future__ import annotations

import structlog

from colette.schemas.common import SecurityFinding

logger = structlog.get_logger(__name__)

_DEFAULT_MIN_CONFIDENCE = 0.8


def filter_by_confidence(
    findings: list[SecurityFinding],
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
) -> list[SecurityFinding]:
    """Remove findings below *min_confidence* and log removals."""
    kept: list[SecurityFinding] = []
    removed = 0
    for f in findings:
        if f.confidence >= min_confidence:
            kept.append(f)
        else:
            removed += 1
            logger.warning(
                "finding_filter.low_confidence",
                finding_id=f.id,
                confidence=f.confidence,
                severity=f.severity,
                category=f.category,
            )
    if removed:
        logger.info(
            "finding_filter.confidence_summary",
            original=len(findings),
            kept=len(kept),
            removed=removed,
        )
    return kept


def deduplicate_findings(findings: list[SecurityFinding]) -> list[SecurityFinding]:
    """Merge findings that share the same (category, severity).

    Locations are concatenated into the first finding of each group.
    """
    groups: dict[tuple[str, str], SecurityFinding] = {}
    merged_count = 0

    for f in findings:
        key = (f.category, f.severity)
        if key not in groups:
            groups[key] = f
        else:
            existing = groups[key]
            # Merge location info into the existing finding.
            new_location = (
                f"{existing.location}; {f.location}" if f.location else existing.location
            )
            groups[key] = existing.model_copy(update={"location": new_location})
            merged_count += 1

    if merged_count:
        logger.info(
            "finding_filter.dedup_summary",
            original=len(findings),
            deduplicated=len(groups),
            merged=merged_count,
        )
    return list(groups.values())
