"""Tests for stage stubs (monitoring only).

Requirements, Design, Implementation, Testing, and Deployment stages are now
real implementations and have their own test files.
"""

from __future__ import annotations

import pytest

from colette.orchestrator.state import create_initial_state
from colette.schemas.common import StageName, StageStatus
from colette.stages.monitoring.stage import run_stage as monitoring_run


@pytest.fixture
def initial_state() -> dict:
    return dict(create_initial_state("test-project"))


class TestMonitoringStub:
    @pytest.mark.asyncio
    async def test_sets_completed_at(self, initial_state: dict) -> None:
        result = await monitoring_run(initial_state)
        assert result["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_marks_stage_completed(self, initial_state: dict) -> None:
        result = await monitoring_run(initial_state)
        assert result["stage_statuses"][StageName.MONITORING.value] == StageStatus.COMPLETED.value
