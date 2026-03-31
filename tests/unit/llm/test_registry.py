"""Tests for ProjectStatusRegistry."""

from __future__ import annotations

import threading

import pytest

from colette.llm.registry import ProjectNotActiveError, ProjectStatusRegistry


class TestProjectStatusRegistry:
    def test_mark_and_get(self) -> None:
        reg = ProjectStatusRegistry()
        reg.mark("p1", "running")
        assert reg.get("p1") == "running"

    def test_get_unknown_returns_none(self) -> None:
        reg = ProjectStatusRegistry()
        assert reg.get("unknown") is None

    def test_assert_active_passes_for_running(self) -> None:
        reg = ProjectStatusRegistry()
        reg.mark("p1", "running")
        reg.assert_active("p1")  # Should not raise

    def test_assert_active_raises_for_interrupted(self) -> None:
        reg = ProjectStatusRegistry()
        reg.mark("p1", "interrupted")
        with pytest.raises(ProjectNotActiveError, match="interrupted"):
            reg.assert_active("p1")

    def test_assert_active_raises_for_unknown(self) -> None:
        reg = ProjectStatusRegistry()
        with pytest.raises(ProjectNotActiveError, match="None"):
            reg.assert_active("unknown")

    def test_assert_active_raises_for_failed(self) -> None:
        reg = ProjectStatusRegistry()
        reg.mark("p1", "failed")
        with pytest.raises(ProjectNotActiveError):
            reg.assert_active("p1")

    def test_assert_active_raises_for_cancelled(self) -> None:
        reg = ProjectStatusRegistry()
        reg.mark("p1", "cancelled")
        with pytest.raises(ProjectNotActiveError):
            reg.assert_active("p1")

    def test_remove(self) -> None:
        reg = ProjectStatusRegistry()
        reg.mark("p1", "running")
        reg.remove("p1")
        assert reg.get("p1") is None

    def test_remove_unknown_is_safe(self) -> None:
        reg = ProjectStatusRegistry()
        reg.remove("nonexistent")

    def test_running_count(self) -> None:
        reg = ProjectStatusRegistry()
        assert reg.running_count() == 0
        reg.mark("p1", "running")
        assert reg.running_count() == 1
        reg.mark("p2", "running")
        assert reg.running_count() == 2
        reg.mark("p1", "completed")
        assert reg.running_count() == 1

    def test_running_count_excludes_non_running(self) -> None:
        reg = ProjectStatusRegistry()
        reg.mark("p1", "running")
        reg.mark("p2", "interrupted")
        reg.mark("p3", "failed")
        assert reg.running_count() == 1

    def test_mark_overwrites_previous(self) -> None:
        reg = ProjectStatusRegistry()
        reg.mark("p1", "running")
        reg.mark("p1", "completed")
        assert reg.get("p1") == "completed"

    def test_thread_safety(self) -> None:
        """Concurrent marks should not corrupt the registry."""
        reg = ProjectStatusRegistry()
        errors: list[Exception] = []

        def worker(pid: str) -> None:
            try:
                for _ in range(100):
                    reg.mark(pid, "running")
                    reg.get(pid)
                    reg.running_count()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f"p{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


class TestProjectNotActiveError:
    def test_is_runtime_error(self) -> None:
        assert issubclass(ProjectNotActiveError, RuntimeError)

    def test_message_includes_project_id(self) -> None:
        reg = ProjectStatusRegistry()
        reg.mark("proj-42", "interrupted")
        with pytest.raises(ProjectNotActiveError, match="proj-42"):
            reg.assert_active("proj-42")
