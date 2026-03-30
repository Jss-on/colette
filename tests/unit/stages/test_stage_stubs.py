"""Tests for monitoring stage entry point (formerly a stub, now a real stage).

Requirements, Design, Implementation, Testing, and Deployment stages have
their own test files.  The monitoring stage is now fully implemented (Phase 7)
and tested in ``test_monitoring_stage.py``.  This file retains backward-
compatible sanity checks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import DeploymentTarget, StageName, StageStatus
from colette.schemas.deployment import DeploymentToMonitoringHandoff
from colette.stages.monitoring.stage import run_stage as monitoring_run


def _make_state_with_deployment_handoff() -> dict:
    handoff = DeploymentToMonitoringHandoff(
        project_id="test-project",
        deployment_id="deploy-test-20260330",
        targets=[
            DeploymentTarget(
                environment="staging",
                url="https://staging.example.com",
            ),
        ],
        docker_images=["app:latest"],
        slo_targets={"availability": "99.9%"},
        git_ref="main",
        quality_gate_passed=True,
    )
    return {
        "project_id": "test-project",
        "stage_statuses": {},
        "handoffs": {
            StageName.DEPLOYMENT.value: handoff.to_dict(),
        },
    }


class TestMonitoringStage:
    @pytest.mark.asyncio
    async def test_raises_on_missing_deployment_handoff(self) -> None:
        state = {"project_id": "test", "stage_statuses": {}, "handoffs": {}}
        with pytest.raises(ValueError, match="requires a completed Deployment handoff"):
            await monitoring_run(state)

    @pytest.mark.asyncio
    async def test_sets_completed_at(self) -> None:
        state = _make_state_with_deployment_handoff()
        with (
            patch(
                "colette.stages.monitoring.supervisor.run_observability_agent",
                new_callable=AsyncMock,
            ),
            patch(
                "colette.stages.monitoring.supervisor.run_incident_response",
                new_callable=AsyncMock,
            ),
            patch("colette.stages.monitoring.stage.Settings"),
        ):
            result = await monitoring_run(state)
        assert result["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_marks_stage_completed(self) -> None:
        state = _make_state_with_deployment_handoff()
        with (
            patch(
                "colette.stages.monitoring.supervisor.run_observability_agent",
                new_callable=AsyncMock,
            ),
            patch(
                "colette.stages.monitoring.supervisor.run_incident_response",
                new_callable=AsyncMock,
            ),
            patch("colette.stages.monitoring.stage.Settings"),
        ):
            result = await monitoring_run(state)
        assert (
            result["stage_statuses"][StageName.MONITORING.value]
            == StageStatus.COMPLETED.value
        )
