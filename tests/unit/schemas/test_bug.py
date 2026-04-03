"""Tests for bug report schema (Phase 5)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from colette.schemas.backlog import BacklogPriority
from colette.schemas.bug import BugReport


class TestBugReport:
    def test_minimal(self) -> None:
        bug = BugReport(id="BUG-001", title="Crash", description="App crashes")
        assert bug.id == "BUG-001"
        assert bug.severity == BacklogPriority.P2_MEDIUM
        assert bug.regression_test_needed is True
        assert bug.affected_stage is None

    def test_full(self) -> None:
        bug = BugReport(
            id="BUG-002",
            work_item_id="WI-001",
            title="Login fails",
            description="Login returns 500",
            reproduction_steps=["Go to login", "Enter credentials", "Click submit"],
            severity=BacklogPriority.P0_CRITICAL,
            affected_stage="implementation",
            root_cause_analysis="Missing null check",
        )
        assert len(bug.reproduction_steps) == 3
        assert bug.affected_stage == "implementation"

    def test_frozen(self) -> None:
        bug = BugReport(id="B", title="t", description="d")
        with pytest.raises(ValidationError):
            bug.title = "new"  # type: ignore[misc]

    def test_serialization_roundtrip(self) -> None:
        bug = BugReport(
            id="BUG-003",
            title="Test bug",
            description="desc",
            reproduction_steps=["step 1"],
        )
        data = bug.model_dump()
        restored = BugReport.model_validate(data)
        assert restored == bug
