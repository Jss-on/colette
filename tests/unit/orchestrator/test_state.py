"""Tests for PipelineState and create_initial_state."""

from __future__ import annotations

from colette.orchestrator.state import STAGE_ORDER, create_initial_state
from colette.schemas.common import StageName, StageStatus


class TestCreateInitialState:
    def test_returns_all_required_keys(self) -> None:
        state = create_initial_state("proj-1")
        assert state["project_id"] == "proj-1"
        assert state["current_stage"] == StageName.REQUIREMENTS.value
        assert state["completed_at"] is None
        assert state["total_tokens_used"] == 0
        assert isinstance(state["handoffs"], dict)
        assert isinstance(state["quality_gate_results"], dict)

    def test_all_stages_pending(self) -> None:
        state = create_initial_state("proj-1")
        for stage in STAGE_ORDER:
            assert state["stage_statuses"][stage] == StageStatus.PENDING.value

    def test_append_only_fields_are_empty_lists(self) -> None:
        state = create_initial_state("proj-1")
        assert state["progress_events"] == []
        assert state["error_log"] == []
        assert state["approval_requests"] == []
        assert state["approval_decisions"] == []

    def test_custom_pipeline_run_id(self) -> None:
        state = create_initial_state("proj-1", pipeline_run_id="custom-run")
        assert state["pipeline_run_id"] == "custom-run"

    def test_default_pipeline_run_id_contains_project_id(self) -> None:
        state = create_initial_state("proj-1")
        assert state["pipeline_run_id"].startswith("proj-1-")


class TestStageOrder:
    def test_has_six_stages(self) -> None:
        assert len(STAGE_ORDER) == 6

    def test_order_matches_sdlc(self) -> None:
        expected = [
            "requirements",
            "design",
            "implementation",
            "testing",
            "deployment",
            "monitoring",
        ]
        assert expected == STAGE_ORDER
