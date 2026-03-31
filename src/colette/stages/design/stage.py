"""Design stage — PRD to architecture, API, DB schema, UI (FR-DES-*, FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.config import Settings
from colette.schemas.common import StageName, StageStatus
from colette.schemas.requirements import RequirementsToDesignHandoff
from colette.stages.design.supervisor import supervise_design

logger = structlog.get_logger(__name__)


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the Design stage.

    Reads the Requirements handoff and produces architecture,
    API specs, DB schema, and UI component specifications as a
    ``DesignToImplementationHandoff``.
    """
    project_id: str = state["project_id"]

    structlog.contextvars.bind_contextvars(stage="design", project_id=project_id)
    try:
        logger.info("stage.start")

        # Retrieve PRD from requirements stage
        req_handoff_data = state.get("handoffs", {}).get(StageName.REQUIREMENTS.value)
        if not req_handoff_data:
            msg = "Design stage requires a completed Requirements handoff in state"
            raise ValueError(msg)
        prd_handoff = RequirementsToDesignHandoff.model_validate(req_handoff_data)

        settings = Settings()
        handoff = await supervise_design(
            project_id=project_id,
            prd_handoff=prd_handoff,
            settings=settings,
        )

        logger.info("stage.complete", endpoints=len(handoff.endpoints))
    finally:
        structlog.contextvars.unbind_contextvars("stage", "project_id")

    return {
        "current_stage": StageName.DESIGN.value,
        "stage_statuses": {
            **state.get("stage_statuses", {}),
            StageName.DESIGN.value: StageStatus.COMPLETED.value,
        },
        "handoffs": {
            **state.get("handoffs", {}),
            StageName.DESIGN.value: handoff.to_dict(),
        },
        "progress_events": [
            {
                "stage": StageName.DESIGN.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ],
    }
