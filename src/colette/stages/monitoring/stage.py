"""Monitoring stage stub — final pipeline stage (FR-ORC-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.schemas.common import StageName, StageStatus

logger = structlog.get_logger()


async def run_stage(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the monitoring stage (stub).

    As the final stage, this marks the pipeline as completed.
    There is no outgoing handoff schema — monitoring is the terminus.
    """
    project_id = state["project_id"]
    logger.info("stage.start", stage="monitoring", project_id=project_id)

    now = datetime.now(UTC).isoformat()
    logger.info("stage.complete", stage="monitoring", project_id=project_id)

    return {
        "current_stage": StageName.MONITORING.value,
        "stage_statuses": {
            **state.get("stage_statuses", {}),
            StageName.MONITORING.value: StageStatus.COMPLETED.value,
        },
        "completed_at": now,
        "progress_events": [
            {
                "stage": StageName.MONITORING.value,
                "status": StageStatus.COMPLETED.value,
                "timestamp": now,
            },
        ],
    }
