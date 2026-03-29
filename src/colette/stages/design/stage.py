"""Design stage stub — produces a dummy architecture handoff (FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.schemas.common import EntitySpec, StageName, StageStatus
from colette.schemas.design import DesignToImplementationHandoff

logger = structlog.get_logger()


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the design stage (stub)."""
    project_id = state["project_id"]
    logger.info("stage.start", stage="design", project_id=project_id)

    handoff = DesignToImplementationHandoff(
        project_id=project_id,
        architecture_summary="Stub architecture — placeholder for real design.",
        tech_stack={"frontend": "Next.js", "backend": "Python/FastAPI", "database": "PostgreSQL"},
        openapi_spec='{"openapi":"3.1.0","info":{"title":"Stub","version":"0.1.0"},"paths":{}}',
        db_entities=[
            EntitySpec(
                name="users",
                fields=[{"name": "id", "type": "uuid", "constraints": "PRIMARY KEY"}],
            ),
        ],
        quality_gate_passed=True,
    )

    logger.info("stage.complete", stage="design", project_id=project_id)
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
