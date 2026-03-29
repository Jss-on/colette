"""Requirements stage stub — produces a dummy PRD handoff (FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.schemas.common import StageName, StageStatus, UserStory
from colette.schemas.requirements import RequirementsToDesignHandoff

logger = structlog.get_logger()


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the requirements stage (stub)."""
    project_id = state["project_id"]
    logger.info("stage.start", stage="requirements", project_id=project_id)

    handoff = RequirementsToDesignHandoff(
        project_id=project_id,
        project_overview="Stub PRD — placeholder for real requirements analysis.",
        functional_requirements=[
            UserStory(
                id="US-REQ-001",
                title="Placeholder story",
                persona="developer",
                goal="validate pipeline flow",
                benefit="end-to-end testing works",
                acceptance_criteria=["Pipeline completes successfully"],
            ),
        ],
        completeness_score=0.90,
        quality_gate_passed=True,
    )

    logger.info("stage.complete", stage="requirements", project_id=project_id)
    return {
        "current_stage": StageName.REQUIREMENTS.value,
        "stage_statuses": {
            **state.get("stage_statuses", {}),
            StageName.REQUIREMENTS.value: StageStatus.COMPLETED.value,
        },
        "handoffs": {
            **state.get("handoffs", {}),
            StageName.REQUIREMENTS.value: handoff.to_dict(),
        },
        "progress_events": [
            {
                "stage": StageName.REQUIREMENTS.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ],
    }
