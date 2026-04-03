"""Tests for CLI UI rendering functions."""

from __future__ import annotations

import dataclasses
from io import StringIO
from typing import Any

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from colette.cli_ui import (
    PIPELINE_STAGES,
    ActivityMode,
    PipelineProgressDisplay,
    StageState,
    build_agent_activity_panel,
    build_conversation_feed,
    build_progress_renderable,
    build_summary_panel,
    render_approval_prompt,
    render_artifact_tree,
    render_config_table,
    render_error,
    render_pipeline_summary,
    render_progress_table,
    render_status_notice,
    render_success,
)
from colette.orchestrator.agent_presence import (
    AgentPresence,
    AgentState,
    ConversationEntry,
)


def _render_to_str(renderable: object) -> str:
    """Render a Rich object to plain text (no ANSI codes)."""
    console = Console(file=StringIO(), no_color=True, width=120, highlight=False)
    console.print(renderable, highlight=False)
    return console.file.getvalue()  # type: ignore[union-attr]


# ── render_progress_table ─────────────────────────────────────────────


class TestRenderProgressTable:
    def test_returns_table(self) -> None:
        table = render_progress_table([])
        assert isinstance(table, Table)

    def test_has_correct_columns(self) -> None:
        table = render_progress_table([])
        col_names = [c.header for c in table.columns]
        assert "Stage" in col_names
        assert "Status" in col_names

    def test_renders_events(self) -> None:
        events = [
            {
                "stage": "requirements",
                "status": "completed",
                "elapsed_seconds": 23,
                "tokens_used": 100,
            },
            {"stage": "design", "status": "running", "elapsed_seconds": 5},
            {"stage": "implementation", "status": "pending"},
        ]
        table = render_progress_table(events)
        output = _render_to_str(table)
        assert "requirements" in output
        assert "design" in output
        assert "implementation" in output

    def test_renders_interrupted_status(self) -> None:
        events = [{"stage": "design", "status": "interrupted"}]
        table = render_progress_table(events)
        output = _render_to_str(table)
        assert "interrupted" in output

    def test_renders_cancelled_status(self) -> None:
        events = [{"stage": "testing", "status": "cancelled"}]
        table = render_progress_table(events)
        output = _render_to_str(table)
        assert "cancelled" in output

    def test_handles_unknown_status(self) -> None:
        events = [{"stage": "x", "status": "weird"}]
        table = render_progress_table(events)
        output = _render_to_str(table)
        assert "weird" in output

    def test_handles_missing_fields(self) -> None:
        events = [{}]
        table = render_progress_table(events)
        output = _render_to_str(table)
        assert "?" in output or "unknown" in output


# ── render_approval_prompt ────────────────────────────────────────────


class TestRenderApprovalPrompt:
    def test_returns_text(self) -> None:
        result = render_approval_prompt({"stage": "deployment", "tier": "T0"})
        assert isinstance(result, Text)

    def test_includes_stage_and_risk(self) -> None:
        result = render_approval_prompt(
            {"stage": "deployment", "tier": "T0", "risk_assessment": "high"}
        )
        output = _render_to_str(result)
        assert "deployment" in output
        assert "high" in output

    def test_handles_missing_fields(self) -> None:
        result = render_approval_prompt({})
        output = _render_to_str(result)
        assert "?" in output or "approval required" in output


# ── render_pipeline_summary ───────────────────────────────────────────


class TestRenderPipelineSummary:
    def test_returns_panel(self) -> None:
        panel = render_pipeline_summary({"status": "completed", "project_id": "p1"})
        assert isinstance(panel, Panel)

    def test_completed_status(self) -> None:
        data = {
            "project_id": "proj-123",
            "status": "completed",
            "current_stage": "monitoring",
            "total_tokens": 5000,
            "thread_id": "t-1",
        }
        output = _render_to_str(render_pipeline_summary(data))
        assert "proj-123" in output
        assert "completed" in output
        assert "5,000" in output

    def test_failed_status(self) -> None:
        output = _render_to_str(render_pipeline_summary({"status": "failed"}))
        assert "failed" in output

    def test_interrupted_status(self) -> None:
        output = _render_to_str(render_pipeline_summary({"status": "interrupted"}))
        assert "interrupted" in output


# ── render_artifact_tree ──────────────────────────────────────────────


class TestRenderArtifactTree:
    def test_returns_tree(self) -> None:
        tree = render_artifact_tree([])
        assert isinstance(tree, Tree)

    def test_renders_files(self) -> None:
        files = [
            {"path": "src/main.py", "language": "python", "size_bytes": 1234},
            {"path": "README.md", "size_bytes": 500},
        ]
        tree = render_artifact_tree(files)
        output = _render_to_str(tree)
        assert "src/main.py" in output
        # [python] is consumed as Rich markup — verify size instead
        assert "1,234 bytes" in output
        assert "README.md" in output

    def test_handles_minimal_file_info(self) -> None:
        files = [{"path": "file.txt"}]
        tree = render_artifact_tree(files)
        output = _render_to_str(tree)
        assert "file.txt" in output


# ── render_config_table ───────────────────────────────────────────────


class TestRenderConfigTable:
    def test_returns_table(self) -> None:
        table = render_config_table({"key": "value"})
        assert isinstance(table, Table)

    def test_redacts_secrets(self) -> None:
        settings = {
            "api_key": "super-secret-123",
            "database_url": "postgres://localhost",
            "neo4j_password": "pass123",
            "cohere_api_key": "key-456",
        }
        table = render_config_table(settings, redact_secrets=True)
        output = _render_to_str(table)
        assert "super-secret-123" not in output
        assert "pass123" not in output
        assert "key-456" not in output
        assert "***" in output
        assert "postgres://localhost" in output

    def test_no_redact_when_disabled(self) -> None:
        settings = {"api_key": "visible-key"}
        table = render_config_table(settings, redact_secrets=False)
        output = _render_to_str(table)
        assert "visible-key" in output

    def test_sorts_keys(self) -> None:
        settings = {"zebra": "z", "alpha": "a"}
        table = render_config_table(settings)
        output = _render_to_str(table)
        alpha_pos = output.find("alpha")
        zebra_pos = output.find("zebra")
        assert alpha_pos < zebra_pos


# ── render_status_notice ──────────────────────────────────────────────


class TestRenderStatusNotice:
    def test_interrupted_notice(self) -> None:
        console = Console(file=StringIO(), no_color=True, width=120, highlight=False)
        import colette.cli_ui

        original = colette.cli_ui.console
        colette.cli_ui.console = console
        try:
            render_status_notice("interrupted", "proj-1")
            output = console.file.getvalue()  # type: ignore[union-attr]
            assert "interrupted" in output
            assert "proj-1" in output
        finally:
            colette.cli_ui.console = original

    def test_cancelled_notice(self) -> None:
        console = Console(file=StringIO(), no_color=True, width=120, highlight=False)
        import colette.cli_ui

        original = colette.cli_ui.console
        colette.cli_ui.console = console
        try:
            render_status_notice("cancelled", "proj-2")
            output = console.file.getvalue()  # type: ignore[union-attr]
            assert "cancelled" in output
        finally:
            colette.cli_ui.console = original

    def test_other_status_does_nothing(self) -> None:
        console = Console(file=StringIO(), no_color=True, width=120, highlight=False)
        import colette.cli_ui

        original = colette.cli_ui.console
        colette.cli_ui.console = console
        try:
            render_status_notice("running", "proj-3")
            output = console.file.getvalue()  # type: ignore[union-attr]
            assert output.strip() == ""
        finally:
            colette.cli_ui.console = original


# ── render_error / render_success ─────────────────────────────────────


class TestRenderMessages:
    def test_render_error(self) -> None:
        console = Console(file=StringIO(), no_color=True, width=120, highlight=False)
        import colette.cli_ui

        original = colette.cli_ui.console
        colette.cli_ui.console = console
        try:
            render_error("something broke")
            output = console.file.getvalue()  # type: ignore[union-attr]
            assert "something broke" in output
        finally:
            colette.cli_ui.console = original

    def test_render_success(self) -> None:
        console = Console(file=StringIO(), no_color=True, width=120, highlight=False)
        import colette.cli_ui

        original = colette.cli_ui.console
        colette.cli_ui.console = console
        try:
            render_success("all good")
            output = console.file.getvalue()  # type: ignore[union-attr]
            assert "all good" in output
        finally:
            colette.cli_ui.console = original


# ── StageState ───────────────────────────────────────────────────────


class TestStageState:
    def test_defaults(self) -> None:
        s = StageState(name="design")
        assert s.name == "design"
        assert s.status == "pending"
        assert s.elapsed_seconds == 0.0
        assert s.tokens_used == 0
        assert s.agent == ""
        assert s.message == ""

    def test_frozen(self) -> None:
        s = StageState(name="testing")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.name = "other"  # type: ignore[misc]

    def test_custom_values(self) -> None:
        s = StageState(
            name="design",
            status="running",
            elapsed_seconds=12.5,
            tokens_used=400,
            agent="System Architect",
            message="Generating architecture...",
        )
        assert s.status == "running"
        assert s.agent == "System Architect"


# ── build_progress_renderable ────────────────────────────────────────


class TestBuildProgressRenderable:
    def _make_stages(self, **overrides: dict[str, Any]) -> tuple[StageState, ...]:
        """Create default pending stages with optional overrides."""
        stages = []
        for name in PIPELINE_STAGES:
            kwargs = overrides.get(name, {})
            stages.append(StageState(name=name, **kwargs))
        return tuple(stages)

    def test_all_pending(self) -> None:
        stages = self._make_stages()
        result = build_progress_renderable(stages)
        output = _render_to_str(result)
        for name in (
            "requirements",
            "design",
            "implementation",
            "testing",
            "deployment",
            "monitoring",
        ):
            assert name in output

    def test_completed_stage_shows_status_word(self) -> None:
        stages = self._make_stages(
            requirements={"status": "completed", "elapsed_seconds": 23.0},
        )
        result = build_progress_renderable(stages)
        output = _render_to_str(result)
        assert "completed" in output

    def test_running_stage_shows_running(self) -> None:
        stages = self._make_stages(
            design={"status": "running"},
        )
        result = build_progress_renderable(stages)
        output = _render_to_str(result)
        assert "running" in output

    def test_failed_stage_shows_failed(self) -> None:
        stages = self._make_stages(
            testing={"status": "failed"},
        )
        result = build_progress_renderable(stages, error_message="Test suite crashed")
        output = _render_to_str(result)
        assert "failed" in output
        assert "Test suite crashed" in output

    def test_elapsed_shown_for_completed(self) -> None:
        stages = self._make_stages(
            requirements={"status": "completed", "elapsed_seconds": 23.0},
        )
        output = _render_to_str(build_progress_renderable(stages))
        assert "23" in output

    def test_returns_text(self) -> None:
        stages = self._make_stages()
        result = build_progress_renderable(stages)
        assert isinstance(result, Text)


# ── build_summary_panel ──────────────────────────────────────────────


class TestBuildSummaryPanel:
    def _completed_stages(self) -> tuple[StageState, ...]:
        return tuple(
            StageState(name=n, status="completed", elapsed_seconds=10.0, tokens_used=500)
            for n in PIPELINE_STAGES
        )

    def test_completed_summary(self) -> None:
        stages = self._completed_stages()
        result = build_summary_panel(stages, "proj-123", "completed")
        assert isinstance(result, Text)
        output = _render_to_str(result)
        assert "proj-123" in output
        assert "completed" in output
        assert "3,000" in output  # 6 stages * 500 tokens
        assert "60" in output or "1m" in output  # 6 stages * 10s

    def test_failed_summary_includes_error(self) -> None:
        stages = (
            StageState(
                name="requirements",
                status="completed",
                elapsed_seconds=10.0,
                tokens_used=200,
            ),
            StageState(name="design", status="failed"),
            *(StageState(name=n) for n in PIPELINE_STAGES[2:]),
        )
        result = build_summary_panel(
            stages,
            "proj-456",
            "failed",
            error_message="Design agent crashed",
        )
        output = _render_to_str(result)
        assert "failed" in output
        assert "Design agent crashed" in output
        assert "1/6" in output  # 1 completed out of 6

    def test_returns_text(self) -> None:
        stages = self._completed_stages()
        result = build_summary_panel(stages, "p", "completed")
        assert isinstance(result, Text)


# ── PipelineProgressDisplay ──────────────────────────────────────────


class TestPipelineProgressDisplay:
    def test_initial_state_all_pending(self) -> None:
        d = PipelineProgressDisplay("proj-1")
        assert not d.is_done
        assert d.project_id == "proj-1"
        for stage in d.stages:
            assert stage.status == "pending"

    def test_stage_started(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event({"event_type": "stage_started", "stage": "requirements"})
        assert d.stages[0].status == "running"

    def test_stage_completed(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event({"event_type": "stage_started", "stage": "requirements"})
        d.process_event(
            {
                "event_type": "stage_completed",
                "stage": "requirements",
                "elapsed_seconds": 23.5,
                "tokens_used": 1200,
            }
        )
        assert d.stages[0].status == "completed"
        assert d.stages[0].elapsed_seconds == 23.5
        assert d.stages[0].tokens_used == 1200

    def test_stage_failed(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event({"event_type": "stage_started", "stage": "design"})
        d.process_event(
            {
                "event_type": "stage_failed",
                "stage": "design",
                "message": "Architect timed out",
            }
        )
        assert d.stages[1].status == "failed"
        assert d.error_message == "Architect timed out"

    def test_agent_started_updates_message(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event({"event_type": "stage_started", "stage": "design"})
        d.process_event(
            {
                "event_type": "agent_started",
                "stage": "design",
                "agent": "System Architect",
                "message": "Generating architecture...",
            }
        )
        assert d.stages[1].agent == "System Architect"
        assert d.stages[1].message == "Generating architecture..."

    def test_agent_completed_clears_message(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event({"event_type": "stage_started", "stage": "design"})
        d.process_event(
            {
                "event_type": "agent_started",
                "stage": "design",
                "agent": "Architect",
                "message": "Working...",
            }
        )
        d.process_event({"event_type": "agent_completed", "stage": "design"})
        assert d.stages[1].agent == ""
        assert d.stages[1].message == ""

    def test_pipeline_completed(self) -> None:
        d = PipelineProgressDisplay("p")
        terminal = d.process_event({"event_type": "pipeline_completed"})
        assert terminal is True
        assert d.is_done
        assert d.final_status == "completed"

    def test_pipeline_completed_after_gate_failure_shows_failed(self) -> None:
        """When a gate fails but the graph exits normally, status should be 'failed'."""
        d = PipelineProgressDisplay("p")
        d.process_event(
            {
                "event_type": "gate_failed",
                "stage": "requirements",
                "message": "Completeness score 0.62 < 0.80",
            }
        )
        terminal = d.process_event({"event_type": "pipeline_completed"})
        assert terminal is True
        assert d.final_status == "failed"
        assert "Completeness" in d.error_message

    def test_pipeline_failed(self) -> None:
        d = PipelineProgressDisplay("p")
        terminal = d.process_event(
            {
                "event_type": "pipeline_failed",
                "message": "Fatal error",
            }
        )
        assert terminal is True
        assert d.is_done
        assert d.final_status == "failed"
        assert d.error_message == "Fatal error"

    def test_render_returns_text_when_running_default_mode(self) -> None:
        d = PipelineProgressDisplay("p")
        result = d.render()
        assert isinstance(result, Text)

    def test_render_returns_text_when_running_minimal(self) -> None:
        d = PipelineProgressDisplay("p", activity_mode=ActivityMode.MINIMAL)
        result = d.render()
        assert isinstance(result, Text)

    def test_render_returns_text_when_done(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event({"event_type": "pipeline_completed"})
        result = d.render()
        assert isinstance(result, Text)

    def test_unknown_stage_ignored(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event({"event_type": "stage_started", "stage": "unknown_stage"})
        # All stages remain pending — no crash
        for stage in d.stages:
            assert stage.status == "pending"

    def test_gate_events_do_not_crash(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event({"event_type": "gate_passed", "stage": "design"})
        d.process_event({"event_type": "gate_failed", "stage": "design", "message": "Blocked"})
        assert d.stages[1].status == "failed"

    def test_complete_event_alias(self) -> None:
        """The SSE endpoint sends 'complete' as a terminal alias."""
        d = PipelineProgressDisplay("p")
        terminal = d.process_event({"event_type": "complete"})
        assert terminal is True
        assert d.is_done


# ── Phase 7: build_agent_activity_panel ─────────────────────────────


class TestBuildAgentActivityPanel:
    def test_returns_text(self) -> None:
        result = build_agent_activity_panel(())
        assert isinstance(result, Text)

    def test_renders_active_agents(self) -> None:
        agents = (
            AgentPresence(
                agent_id="arch",
                display_name="System Architect",
                stage="design",
                state=AgentState.THINKING,
                activity="Designing schema",
            ),
            AgentPresence(
                agent_id="api",
                display_name="API Designer",
                stage="design",
                state=AgentState.IDLE,
            ),
        )
        result = build_agent_activity_panel(agents)
        output = _render_to_str(result)
        assert "System Architect" in output
        assert "thinking" in output
        assert "Designing schema" in output
        # IDLE agents are not shown in the new style.
        assert "API Designer" not in output

    def test_empty_agents(self) -> None:
        result = build_agent_activity_panel(())
        output = _render_to_str(result)
        # Empty Text produces empty output.
        assert output.strip() == ""

    def test_handoff_shows_target(self) -> None:
        agents = (
            AgentPresence(
                agent_id="arch",
                display_name="Architect",
                stage="design",
                state=AgentState.HANDING_OFF,
                activity="architecture.yaml",
                target_agent="API Designer",
            ),
        )
        output = _render_to_str(build_agent_activity_panel(agents))
        assert "API Designer" in output


# ── Phase 7: build_conversation_feed ────────────────────────────────


class TestBuildConversationFeed:
    def test_returns_text(self) -> None:
        result = build_conversation_feed(())
        assert isinstance(result, Text)

    def test_renders_entries(self) -> None:
        entries = (
            ConversationEntry(
                agent_id="a",
                display_name="Architect",
                stage="design",
                message="Generated schema",
            ),
        )
        output = _render_to_str(build_conversation_feed(entries))
        assert "Architect" in output
        assert "Generated schema" in output

    def test_respects_max_lines(self) -> None:
        entries = tuple(
            ConversationEntry(
                agent_id="a",
                display_name="A",
                stage="s",
                message=f"msg-{i}",
            )
            for i in range(20)
        )
        output = _render_to_str(build_conversation_feed(entries, max_lines=5))
        # Only last 5 should appear
        assert "msg-15" in output
        assert "msg-19" in output
        assert "msg-0" not in output

    def test_empty_entries(self) -> None:
        result = build_conversation_feed(())
        output = _render_to_str(result)
        # Empty Text produces empty output.
        assert output.strip() == ""

    def test_target_agent_shown(self) -> None:
        entries = (
            ConversationEntry(
                agent_id="a",
                display_name="Architect",
                stage="design",
                message="Handoff",
                target_agent="API Designer",
            ),
        )
        output = _render_to_str(build_conversation_feed(entries))
        assert "API Designer" in output


# ── Phase 7: PipelineProgressDisplay modes ──────────────────────────


class TestPipelineProgressDisplayModes:
    def test_minimal_mode_returns_text(self) -> None:
        d = PipelineProgressDisplay("p", activity_mode=ActivityMode.MINIMAL)
        result = d.render()
        assert isinstance(result, Text)

    def test_status_mode_returns_text(self) -> None:
        d = PipelineProgressDisplay("p", activity_mode=ActivityMode.STATUS)
        result = d.render()
        assert isinstance(result, Text)

    def test_conversation_mode_returns_text(self) -> None:
        d = PipelineProgressDisplay("p", activity_mode=ActivityMode.CONVERSATION)
        result = d.render()
        assert isinstance(result, Text)

    def test_verbose_mode_returns_text(self) -> None:
        d = PipelineProgressDisplay("p", activity_mode=ActivityMode.VERBOSE)
        result = d.render()
        assert isinstance(result, Text)

    def test_done_always_returns_text(self) -> None:
        """All modes return summary Text when pipeline is done."""
        for mode in ActivityMode:
            d = PipelineProgressDisplay("p", activity_mode=mode)
            d.process_event({"event_type": "pipeline_completed"})
            assert isinstance(d.render(), Text)


# ── Phase 7: PipelineProgressDisplay new event handling ─────────────


class TestPipelineProgressDisplayPresenceEvents:
    def test_agent_thinking_updates_presence(self) -> None:
        d = PipelineProgressDisplay("p", activity_mode=ActivityMode.STATUS)
        d.process_event(
            {
                "event_type": "agent_thinking",
                "agent": "Architect",
                "stage": "design",
                "message": "Thinking about schema...",
                "model": "claude-sonnet",
            }
        )
        assert len(d.agents) == 1
        assert d.agents[0].state == AgentState.THINKING
        assert d.agents[0].activity == "Thinking about schema..."

    def test_agent_tool_call_updates_presence(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event(
            {
                "event_type": "agent_tool_call",
                "agent": "Backend Dev",
                "stage": "implementation",
                "message": "Running code generator",
            }
        )
        assert d.agents[0].state == AgentState.TOOL_USE

    def test_agent_reviewing_updates_presence(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event(
            {
                "event_type": "agent_reviewing",
                "agent": "Reviewer",
                "stage": "testing",
                "message": "Reviewing test output",
            }
        )
        assert d.agents[0].state == AgentState.REVIEWING

    def test_agent_state_changed_with_explicit_state(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event(
            {
                "event_type": "agent_state_changed",
                "agent": "Architect",
                "stage": "design",
                "agent_state": "done",
            }
        )
        assert d.agents[0].state == AgentState.DONE

    def test_agent_handoff_sets_target(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event(
            {
                "event_type": "agent_handoff",
                "agent": "Architect",
                "stage": "design",
                "message": "architecture.yaml",
                "target_agent": "API Designer",
            }
        )
        assert d.agents[0].state == AgentState.HANDING_OFF
        assert d.agents[0].target_agent == "API Designer"
        # Also adds a conversation entry
        assert len(d.conversation) == 1

    def test_agent_message_adds_conversation(self) -> None:
        d = PipelineProgressDisplay("p")
        d.process_event(
            {
                "event_type": "agent_message",
                "agent": "Supervisor",
                "stage": "design",
                "message": "Please generate the API spec",
                "target_agent": "API Designer",
            }
        )
        assert len(d.conversation) == 1
        assert d.conversation[0].message == "Please generate the API spec"
        assert d.conversation[0].target_agent == "API Designer"

    def test_agent_message_ring_buffer_trims(self) -> None:
        d = PipelineProgressDisplay("p")
        for i in range(55):
            d.process_event(
                {
                    "event_type": "agent_message",
                    "agent": "A",
                    "stage": "s",
                    "message": f"msg-{i}",
                }
            )
        assert len(d.conversation) == 50

    def test_unknown_event_type_no_crash(self) -> None:
        d = PipelineProgressDisplay("p")
        result = d.process_event({"event_type": "totally_unknown_event"})
        assert result is False
