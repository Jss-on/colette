"""Tests for Phase 6 — structured console logging."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

# ── CLI console renderer ─────────────────────────────────────────────


class TestCliConsoleRenderer:
    """cli_console_renderer formats log events with pipeline context tags."""

    def _make_event(self, **kwargs: Any) -> dict[str, Any]:
        """Build a minimal structlog event dict."""
        defaults: dict[str, Any] = {
            "event": "stage.start",
            "timestamp": "2026-03-31T14:02:31Z",
            "log_level": "info",
            "logger_name": "colette.stages.requirements.stage",
        }
        defaults.update(kwargs)
        return defaults

    def test_formats_stage_tag(self) -> None:
        from colette.observability.logging import cli_console_renderer

        result = cli_console_renderer(None, "info", self._make_event(stage="requirements"))
        assert "[stage:requirements]" in result
        assert "stage.start" in result

    def test_formats_agent_tag(self) -> None:
        from colette.observability.logging import cli_console_renderer

        result = cli_console_renderer(
            None, "info", self._make_event(stage="design", agent="architect")
        )
        assert "[stage:design]" in result
        assert "[agent:architect]" in result

    def test_formats_model_tag(self) -> None:
        from colette.observability.logging import cli_console_renderer

        result = cli_console_renderer(
            None,
            "info",
            self._make_event(stage="design", agent="architect", model="claude-sonnet"),
        )
        assert "[stage:design]" in result
        assert "[agent:architect]" in result
        assert "[model:claude-sonnet]" in result

    def test_no_tags_when_no_context(self) -> None:
        from colette.observability.logging import cli_console_renderer

        result = cli_console_renderer(None, "info", self._make_event())
        assert "[stage:" not in result
        assert "[agent:" not in result
        assert "stage.start" in result

    def test_includes_extra_keys(self) -> None:
        from colette.observability.logging import cli_console_renderer

        result = cli_console_renderer(
            None,
            "info",
            self._make_event(stage="requirements", completeness=0.92),
        )
        assert "completeness=0.92" in result

    def test_includes_timestamp(self) -> None:
        from colette.observability.logging import cli_console_renderer

        result = cli_console_renderer(None, "info", self._make_event())
        assert "2026-03-31T14:02:31Z" in result

    def test_includes_log_level(self) -> None:
        from colette.observability.logging import cli_console_renderer

        result = cli_console_renderer(None, "info", self._make_event(log_level="warning"))
        assert "WARNING" in result

    def test_returns_string(self) -> None:
        from colette.observability.logging import cli_console_renderer

        result = cli_console_renderer(None, "info", self._make_event())
        assert isinstance(result, str)

    def test_skips_internal_keys(self) -> None:
        """Keys starting with _ should not appear in output."""
        from colette.observability.logging import cli_console_renderer

        result = cli_console_renderer(None, "info", self._make_event(_internal="secret"))
        assert "_internal" not in result
        assert "secret" not in result


# ── configure_logging uses custom renderer ───────────────────────────


class TestConfigureLoggingConsoleRenderer:
    """configure_logging('console') should use cli_console_renderer."""

    def test_console_format_uses_custom_renderer(self) -> None:
        from colette.observability.logging import configure_logging

        configure_logging(log_level="INFO", log_format="console")

        # We just verify configure_logging doesn't crash with "console".
        # Functional format verification is in TestCliConsoleRenderer.

    def test_json_format_uses_json_renderer(self) -> None:
        from colette.observability.logging import configure_logging

        configure_logging(log_level="INFO", log_format="json")
        # Should not raise.


# ── Stage contextvars binding ────────────────────────────────────────


class TestStageContextBinding:
    """Stage run_stage() functions should bind context via structlog.contextvars."""

    @pytest.mark.asyncio
    async def test_requirements_stage_binds_context(self) -> None:
        """requirements stage should call bind_contextvars with stage + project_id."""
        from unittest.mock import MagicMock

        with (
            patch("colette.stages.requirements.stage.structlog") as mock_sl,
            patch("colette.stages.requirements.stage.supervise_requirements") as mock_sup,
            patch("colette.stages.requirements.stage.Settings"),
        ):
            mock_sl.get_logger.return_value = MagicMock()
            mock_handoff = MagicMock()
            mock_handoff.completeness_score = 0.9
            mock_handoff.to_dict.return_value = {}
            mock_sup.return_value = mock_handoff

            from colette.stages.requirements.stage import run_stage

            await run_stage({"project_id": "proj-ctx", "user_request": "test"})

        mock_sl.contextvars.bind_contextvars.assert_called_once_with(
            stage="requirements", project_id="proj-ctx"
        )
        mock_sl.contextvars.unbind_contextvars.assert_called_once_with("stage", "project_id")

    @pytest.mark.asyncio
    async def test_design_stage_binds_context(self) -> None:
        """design stage should call bind_contextvars with stage + project_id."""
        from unittest.mock import MagicMock

        with (
            patch("colette.stages.design.stage.structlog") as mock_sl,
            patch("colette.stages.design.stage.supervise_design") as mock_sup,
            patch("colette.stages.design.stage.RequirementsToDesignHandoff"),
            patch("colette.stages.design.stage.Settings"),
        ):
            mock_sl.get_logger.return_value = MagicMock()
            mock_handoff = MagicMock()
            mock_handoff.endpoints = []
            mock_handoff.to_dict.return_value = {}
            mock_sup.return_value = mock_handoff

            from colette.stages.design.stage import run_stage

            state = {
                "project_id": "proj-ctx2",
                "handoffs": {"requirements": {"some": "data"}},
            }
            await run_stage(state)

        mock_sl.contextvars.bind_contextvars.assert_called_once_with(
            stage="design", project_id="proj-ctx2"
        )
        mock_sl.contextvars.unbind_contextvars.assert_called_once_with("stage", "project_id")

    @pytest.mark.asyncio
    async def test_unbind_called_even_on_error(self) -> None:
        """contextvars should be unbound even if stage raises."""
        from unittest.mock import MagicMock

        with (
            patch("colette.stages.requirements.stage.structlog") as mock_sl,
            patch(
                "colette.stages.requirements.stage.supervise_requirements",
                side_effect=RuntimeError("LLM failed"),
            ),
            patch("colette.stages.requirements.stage.Settings"),
        ):
            mock_sl.get_logger.return_value = MagicMock()

            from colette.stages.requirements.stage import run_stage

            with pytest.raises(RuntimeError, match="LLM failed"):
                await run_stage({"project_id": "proj-err", "user_request": "test"})

        mock_sl.contextvars.unbind_contextvars.assert_called_once_with("stage", "project_id")
