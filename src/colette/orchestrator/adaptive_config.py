"""Adaptive configuration tuning based on retrospective analysis (Phase 6)."""

from __future__ import annotations

from colette.schemas.retrospective import SprintRetrospective

# Gate score thresholds for adaptive adjustment.
_HIGH_PASS_THRESHOLD = 0.95  # consistently passing -> tighten
_LOW_PASS_THRESHOLD = 0.60  # consistently failing -> loosen
_TIGHTEN_STEP = 0.05
_LOOSEN_STEP = 0.05

# Rework threshold for model tier upgrade.
_REWORK_UPGRADE_THRESHOLD = 2


def adjust_gate_thresholds(
    retrospective: SprintRetrospective,
    current_thresholds: dict[str, float] | None = None,
) -> dict[str, float]:
    """Adjust gate thresholds based on sprint performance.

    - Tighten thresholds for stages with high pass rates (> 0.95)
    - Loosen thresholds for stages with consistently low scores (< 0.60)

    Returns a new dict of adjusted thresholds.
    """
    thresholds = dict(current_thresholds or {})

    for stage, score in retrospective.gate_scores.items():
        current = thresholds.get(stage, 0.80)
        if score >= _HIGH_PASS_THRESHOLD:
            thresholds[stage] = min(current + _TIGHTEN_STEP, 0.99)
        elif score <= _LOW_PASS_THRESHOLD:
            thresholds[stage] = max(current - _LOOSEN_STEP, 0.50)
        else:
            thresholds[stage] = current

    return thresholds


def adjust_model_tiers(
    retrospective: SprintRetrospective,
    current_tiers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Suggest model tier upgrades for stages needing more rework.

    Stages with >= 2 rework cycles get upgraded:
      validation -> execution -> planning

    Returns a new dict of tier assignments.
    """
    tiers = dict(current_tiers or {})
    _upgrade_order = ["validation", "execution", "planning"]

    for stage, rework_count in retrospective.rework_by_stage.items():
        if rework_count >= _REWORK_UPGRADE_THRESHOLD:
            current = tiers.get(stage, "execution")
            try:
                idx = _upgrade_order.index(current)
                if idx < len(_upgrade_order) - 1:
                    tiers[stage] = _upgrade_order[idx + 1]
            except ValueError:
                pass

    return tiers
