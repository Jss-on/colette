"""Tests for CLI UI rendering functions."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from colette.cli_ui import (
    render_approval_prompt,
    render_artifact_tree,
    render_config_table,
    render_error,
    render_pipeline_summary,
    render_progress_table,
    render_status_notice,
    render_success,
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
    def test_returns_panel(self) -> None:
        panel = render_approval_prompt({"stage": "deployment", "tier": "T0"})
        assert isinstance(panel, Panel)

    def test_includes_stage_and_tier(self) -> None:
        panel = render_approval_prompt(
            {"stage": "deployment", "tier": "T0", "risk_assessment": "high"}
        )
        output = _render_to_str(panel)
        assert "deployment" in output
        assert "T0" in output
        assert "high" in output

    def test_handles_missing_fields(self) -> None:
        panel = render_approval_prompt({})
        output = _render_to_str(panel)
        assert "?" in output or "N/A" in output


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
