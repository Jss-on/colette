"""Structural requirements completeness scoring.

Replaces ``AnalysisResult.completeness_score`` (LLM self-assessment)
with a deterministic penalty/bonus model.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class CompletenessBreakdown(NamedTuple):
    base_score: float  # always 1.0
    penalties: tuple[tuple[str, float], ...]
    bonuses: tuple[tuple[str, float], ...]
    final_score: float


def score_completeness(
    project_overview: str,
    user_stories: list[dict],
    nfrs: list[dict],
    tech_constraints: list[dict],
    assumptions: list[dict],
    out_of_scope: list[dict],
    open_questions: list[dict],
) -> CompletenessBreakdown:
    """Score requirements completeness using structural penalties and bonuses."""
    penalties: list[tuple[str, float]] = []
    bonuses: list[tuple[str, float]] = []

    # ── Penalties ────────────────────────────────────────────────────

    if not user_stories:
        penalties.append(("No user stories", 0.30))
    elif len(user_stories) < 3:
        penalties.append(("Fewer than 3 user stories", 0.10))

    if not nfrs:
        penalties.append(("No NFRs", 0.10))

    # Stories without acceptance criteria
    if user_stories:
        stories_without_ac = sum(
            1 for story in user_stories if not _has_acceptance_criteria(story)
        )
        if stories_without_ac > 0:
            penalties.append(("Stories without acceptance criteria", 0.10))

    # Open questions penalty
    if len(open_questions) > 5:
        excess = min(len(open_questions) - 5, 4)  # max 4 * 0.02 = 0.08
        penalties.append((f"{len(open_questions)} open questions (>{5})", round(excess * 0.02, 2)))

    if not tech_constraints:
        penalties.append(("No tech constraints", 0.05))

    if len(project_overview.strip()) < 50:
        penalties.append(("Project overview too short (<50 chars)", 0.10))

    if user_stories and len(user_stories) >= 2:
        priorities = {_get_priority(s) for s in user_stories}
        if len(priorities) <= 1:
            penalties.append(("All stories same priority", 0.05))

    if not out_of_scope:
        penalties.append(("No out-of-scope section", 0.05))

    # ── Bonuses ──────────────────────────────────────────────────────

    if user_stories and all(_count_acceptance_criteria(s) >= 3 for s in user_stories):
        bonuses.append(("Stories with >= 3 acceptance criteria each", 0.05))

    if nfrs and any(_has_measurable_target(nfr) for nfr in nfrs):
        bonuses.append(("NFRs with measurable targets", 0.05))

    if tech_constraints and any(_is_security_constraint(c) for c in tech_constraints):
        bonuses.append(("Security/compliance constraints present", 0.05))

    # ── Calculation ──────────────────────────────────────────────────

    total_penalties = sum(p[1] for p in penalties)
    total_bonuses = sum(b[1] for b in bonuses)
    final_score = max(0.0, min(1.0, 1.0 - total_penalties + total_bonuses))

    return CompletenessBreakdown(
        base_score=1.0,
        penalties=tuple(penalties),
        bonuses=tuple(bonuses),
        final_score=round(final_score, 4),
    )


# ── Internal helpers ─────────────────────────────────────────────────


def _has_acceptance_criteria(story: dict) -> bool:
    ac = story.get("acceptance_criteria", story.get("ac", []))
    if isinstance(ac, list):
        return len(ac) > 0
    if isinstance(ac, str):
        return len(ac.strip()) > 0
    return False


def _count_acceptance_criteria(story: dict) -> int:
    ac = story.get("acceptance_criteria", story.get("ac", []))
    if isinstance(ac, list):
        return len(ac)
    if isinstance(ac, str):
        return len([line for line in ac.strip().splitlines() if line.strip()])
    return 0


def _get_priority(story: dict) -> str:
    return str(story.get("priority", "medium")).lower()


def _has_measurable_target(nfr: dict) -> bool:
    text = str(nfr.get("target", nfr.get("description", "")))
    return bool(re.search(r"\d+\s*(?:ms|%|seconds?|s\b|MB|GB|req)", text))


def _is_security_constraint(constraint: dict) -> bool:
    text = str(constraint.get("description", constraint.get("name", ""))).lower()
    return any(
        keyword in text
        for keyword in ("security", "compliance", "encryption", "auth", "gdpr", "hipaa", "soc2")
    )
