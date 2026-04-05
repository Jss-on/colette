"""Tests for Phase 5 — robust error propagation in pipeline background task."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from colette.orchestrator.event_bus import EventType, PipelineEvent, PipelineEventBus

# ── Runner traceback in PIPELINE_FAILED events ──────────────────────


class TestRunnerPipelineFailedTraceback:
    """runner.run() should include traceback in PIPELINE_FAILED detail."""

    @pytest.mark.asyncio
    async def test_pipeline_failed_includes_traceback(self) -> None:
        """PIPELINE_FAILED event detail must contain 'traceback' key."""
        bus = PipelineEventBus()
        queue = bus.subscribe("proj-tb")

        # Build a minimal runner with a graph that raises.
        with (
            patch("colette.orchestrator.runner.build_pipeline") as mock_bp,
            patch("colette.orchestrator.runner.create_default_registry"),
            patch("colette.orchestrator.runner.project_status_registry"),
        ):
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(side_effect=ValueError("LLM provider unreachable"))
            mock_bp.return_value = mock_graph

            from colette.orchestrator.runner import PipelineRunner

            runner = PipelineRunner(event_bus=bus)
            runner._graph = mock_graph
            runner._active = {}
            runner._tasks = {}

            with pytest.raises(ValueError, match="LLM provider unreachable"):
                await runner.run("proj-tb", user_request="test")

        # Drain queue to find the PIPELINE_FAILED event.
        event = queue.get_nowait()
        assert event.event_type == EventType.PIPELINE_FAILED
        assert "LLM provider unreachable" in event.message
        assert "traceback" in event.detail
        assert "ValueError" in event.detail["traceback"]

    @pytest.mark.asyncio
    async def test_pipeline_failed_traceback_is_string(self) -> None:
        """Traceback in detail must be a string for JSON serialization."""
        bus = PipelineEventBus()
        queue = bus.subscribe("proj-tb2")

        with (
            patch("colette.orchestrator.runner.build_pipeline") as mock_bp,
            patch("colette.orchestrator.runner.create_default_registry"),
            patch("colette.orchestrator.runner.project_status_registry"),
        ):
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
            mock_bp.return_value = mock_graph

            from colette.orchestrator.runner import PipelineRunner

            runner = PipelineRunner(event_bus=bus)
            runner._graph = mock_graph
            runner._active = {}
            runner._tasks = {}

            with pytest.raises(RuntimeError):
                await runner.run("proj-tb2", user_request="test")

        event = queue.get_nowait()
        assert isinstance(event.detail["traceback"], str)


# ── _run_pipeline_bg error handling ──────────────────────────────────


class TestRunPipelineBgNoSessionFactory:
    """_run_pipeline_bg must emit PIPELINE_FAILED when session_factory is None."""

    @pytest.mark.asyncio
    async def test_emits_failed_event(self) -> None:
        from colette.api.routes.projects import _run_pipeline_bg

        runner = MagicMock()
        runner.event_bus = MagicMock(spec=PipelineEventBus)

        with patch("colette.api.routes.projects.project_status_registry"):
            await _run_pipeline_bg(runner, "proj-nosf", "test", None)

        runner.event_bus.emit.assert_called_once()
        event: PipelineEvent = runner.event_bus.emit.call_args[0][0]
        assert event.project_id == "proj-nosf"
        assert event.event_type == EventType.PIPELINE_FAILED
        assert "session" in event.message.lower()

    @pytest.mark.asyncio
    async def test_marks_registry_failed(self) -> None:
        from colette.api.routes.projects import _run_pipeline_bg

        runner = MagicMock()
        runner.event_bus = MagicMock(spec=PipelineEventBus)

        with patch("colette.api.routes.projects.project_status_registry") as mock_reg:
            await _run_pipeline_bg(runner, "proj-nosf2", "test", None)

        # Only "failed" — no "running" since runner.run() never executes.
        mock_reg.mark.assert_called_once_with("proj-nosf2", "failed")


class TestRunPipelineBgSuccessDbFailure:
    """When pipeline succeeds but DB update fails, must emit PIPELINE_FAILED."""

    @pytest.mark.asyncio
    async def test_emits_failed_on_db_error(self) -> None:
        from colette.api.routes.projects import _run_pipeline_bg

        runner = MagicMock()
        runner.run = AsyncMock(return_value={})
        runner.event_bus = MagicMock(spec=PipelineEventBus)

        # Session factory that raises on context entry.
        session_factory = MagicMock()
        bad_session = AsyncMock()
        bad_session.__aenter__ = AsyncMock(side_effect=RuntimeError("DB connection lost"))
        bad_session.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = bad_session

        with patch("colette.api.routes.projects.project_status_registry"):
            await _run_pipeline_bg(runner, "proj-dbfail", "test", session_factory)

        # Find the PIPELINE_FAILED event among emit calls.
        calls = runner.event_bus.emit.call_args_list
        failed = [
            c[0][0]
            for c in calls
            if isinstance(c[0][0], PipelineEvent)
            and c[0][0].event_type == EventType.PIPELINE_FAILED
        ]
        assert len(failed) == 1
        assert failed[0].project_id == "proj-dbfail"
        assert "traceback" in failed[0].detail

    @pytest.mark.asyncio
    async def test_logs_critical_on_db_error(self) -> None:
        from colette.api.routes.projects import _run_pipeline_bg

        runner = MagicMock()
        runner.run = AsyncMock(return_value={})
        runner.event_bus = MagicMock(spec=PipelineEventBus)

        session_factory = MagicMock()
        bad_session = AsyncMock()
        bad_session.__aenter__ = AsyncMock(side_effect=RuntimeError("DB gone"))
        bad_session.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = bad_session

        mock_logger = MagicMock()
        with (
            patch("colette.api.routes.projects.project_status_registry"),
            patch("structlog.get_logger", return_value=mock_logger),
        ):
            await _run_pipeline_bg(runner, "proj-dbcrit", "test", session_factory)

        mock_logger.critical.assert_called_once()


class TestRunPipelineBgErrorPathDbFailure:
    """When pipeline fails AND DB update fails, must log critical."""

    @pytest.mark.asyncio
    async def test_logs_critical_on_double_failure(self) -> None:
        from colette.api.routes.projects import _run_pipeline_bg

        runner = MagicMock()
        runner.run = AsyncMock(side_effect=ValueError("Pipeline exploded"))
        runner.event_bus = MagicMock(spec=PipelineEventBus)

        session_factory = MagicMock()
        bad_session = AsyncMock()
        bad_session.__aenter__ = AsyncMock(side_effect=RuntimeError("DB also dead"))
        bad_session.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = bad_session

        mock_logger = MagicMock()
        with (
            patch("colette.api.routes.projects.project_status_registry"),
            patch("structlog.get_logger", return_value=mock_logger),
        ):
            await _run_pipeline_bg(runner, "proj-double", "test", session_factory)

        mock_logger.critical.assert_called_once()


class TestRunPipelineBgNormalSuccess:
    """Happy path: pipeline succeeds, DB updates succeed."""

    @pytest.mark.asyncio
    async def test_marks_completed(self) -> None:
        from colette.api.routes.projects import _run_pipeline_bg

        runner = MagicMock()
        runner.run = AsyncMock(return_value={})
        runner.event_bus = MagicMock(spec=PipelineEventBus)

        # Working session factory.
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        session_factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = ctx

        with (
            patch("colette.api.routes.projects.project_status_registry") as mock_reg,
            patch("colette.api.routes.projects.ProjectRepository"),
            patch("colette.api.routes.projects.PipelineRunRepository") as mock_rr,
        ):
            mock_rr.return_value.list_for_project = AsyncMock(return_value=[])
            await _run_pipeline_bg(runner, "proj-ok", "test", session_factory)

        # runner.run() manages running→completed; _run_pipeline_bg
        # only marks "completed" on the success path.
        calls = [c[0] for c in mock_reg.mark.call_args_list]
        assert ("proj-ok", "completed") in calls
