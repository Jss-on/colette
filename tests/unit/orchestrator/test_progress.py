"""Tests for progress streaming."""

from __future__ import annotations

from colette.orchestrator.progress import state_to_progress_event
from colette.orchestrator.state import create_initial_state


class TestStateToProgressEvent:
    def test_extracts_fields(self) -> None:
        state = dict(create_initial_state("proj-1"))
        event = state_to_progress_event(state)
        assert event.project_id == "proj-1"
        assert event.stage == "requirements"
        assert event.tokens_used == 0

    def test_elapsed_seconds_positive(self) -> None:
        state = dict(create_initial_state("proj-1"))
        event = state_to_progress_event(state)
        assert event.elapsed_seconds >= 0.0

    def test_handles_missing_started_at(self) -> None:
        state = dict(create_initial_state("proj-1"))
        state["started_at"] = ""
        event = state_to_progress_event(state)
        assert event.elapsed_seconds == 0.0
