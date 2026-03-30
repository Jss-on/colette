"""Requirements stage — NL input to structured PRD (FR-REQ-*, FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.config import Settings
from colette.schemas.common import StageName, StageStatus
from colette.stages.requirements.supervisor import supervise_requirements

logger = structlog.get_logger()


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the Requirements stage.

    Takes the user's natural language project description and produces
    a validated PRD as a ``RequirementsToDesignHandoff``.

    The user request is read from ``state["user_request"]`` (preferred)
    or ``state["metadata"]["user_request"]`` (fallback).
    """
    project_id: str = state["project_id"]
    user_request: str = state.get("user_request", "")
    if not user_request:
        user_request = state.get("metadata", {}).get("user_request", "")

    logger.info("stage.start", stage="requirements", project_id=project_id)

    settings = Settings()
    handoff = await supervise_requirements(
        project_id=project_id,
        user_request=user_request,
        settings=settings,
    )

    logger.info(
        "stage.complete",
        stage="requirements",
        project_id=project_id,
        completeness=handoff.completeness_score,
    )

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
