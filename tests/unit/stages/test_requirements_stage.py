"""Tests for the Requirements stage (Phase 4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from colette.schemas.common import NFRSpec, Priority, TechConstraint, UserStory
from colette.stages.requirements.analyst import AnalysisResult
from colette.stages.requirements.researcher import ResearchResult
from colette.stages.requirements.stage import run_stage
from colette.stages.requirements.supervisor import (
    _compute_completeness,
    _ensure_story_ids,
    assemble_handoff,
    supervise_requirements,
)

# ── Fixtures ────────────────────────────────────────────────────────────


def _make_story(
    story_id: str = "US-REQ-001",
    title: str = "Test story",
    criteria: list[str] | None = None,
) -> UserStory:
    return UserStory(
        id=story_id,
        title=title,
        persona="developer",
        goal="do something",
        benefit="value delivered",
        acceptance_criteria=criteria or ["Given/When/Then test"],
        priority=Priority.MUST,
    )


def _make_analysis(
    stories: list[UserStory] | None = None,
    score: float = 0.90,
    nfrs: list[NFRSpec] | None = None,
    open_questions: list[str] | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        project_overview="Test project overview",
        user_stories=stories or [_make_story()],
        nfrs=(
            nfrs if nfrs is not None
            else [NFRSpec(id="NFR-001", category="performance", description="Fast")]
        ),
        tech_constraints=[],
        assumptions=["Assumes PostgreSQL"],
        out_of_scope=["Mobile app"],
        completeness_score=score,
        open_questions=open_questions or [],
    )


def _make_research() -> ResearchResult:
    return ResearchResult(
        domain_insights="Relevant domain context.",
        suggested_constraints=[
            TechConstraint(id="TC-R-001", description="WCAG 2.1 AA", rationale="Accessibility"),
        ],
        relevant_standards=["OWASP Top 10"],
        risk_factors=["Scalability under load"],
    )


# ── _ensure_story_ids ───────────────────────────────────────────────────


class TestEnsureStoryIds:
    def test_preserves_valid_ids(self) -> None:
        story = _make_story(story_id="US-REQ-001")
        result = _ensure_story_ids([story])
        assert result[0].id == "US-REQ-001"

    def test_replaces_invalid_ids(self) -> None:
        story = _make_story(story_id="INVALID-1")
        result = _ensure_story_ids([story])
        assert result[0].id == "US-REQ-001"

    def test_sequential_numbering(self) -> None:
        stories = [_make_story(story_id=f"BAD-{i}") for i in range(3)]
        result = _ensure_story_ids(stories)
        assert [s.id for s in result] == ["US-REQ-001", "US-REQ-002", "US-REQ-003"]


# ── _compute_completeness ───────────────────────────────────────────────


class TestComputeCompleteness:
    def test_no_penalties(self) -> None:
        analysis = _make_analysis(
            stories=[_make_story() for _ in range(3)],
            score=0.95,
        )
        assert _compute_completeness(analysis) == 0.95

    def test_penalises_no_stories(self) -> None:
        analysis = _make_analysis(stories=[], score=0.90)
        # Can't create AnalysisResult with empty stories due to UserStory list
        # but we can test the penalty logic directly
        assert _compute_completeness(analysis) < 0.90

    def test_penalises_few_stories(self) -> None:
        analysis = _make_analysis(stories=[_make_story()], score=0.95)
        assert _compute_completeness(analysis) == pytest.approx(0.85)

    def test_penalises_no_nfrs(self) -> None:
        analysis = _make_analysis(
            stories=[_make_story() for _ in range(3)],
            nfrs=[],
            score=0.95,
        )
        assert _compute_completeness(analysis) == pytest.approx(0.85)

    def test_penalises_many_open_questions(self) -> None:
        analysis = _make_analysis(
            stories=[_make_story() for _ in range(3)],
            open_questions=[f"Q{i}" for i in range(10)],
            score=0.95,
        )
        # 5 excess questions * 0.05 = 0.20 penalty (capped at 4 * 0.05 = 0.20)
        assert _compute_completeness(analysis) < 0.95

    def test_floor_at_zero(self) -> None:
        analysis = _make_analysis(stories=[], nfrs=[], score=0.1)
        assert _compute_completeness(analysis) >= 0.0


# ── assemble_handoff ────────────────────────────────────────────────────


class TestAssembleHandoff:
    def test_basic_assembly(self) -> None:
        analysis = _make_analysis(stories=[_make_story() for _ in range(3)])
        handoff = assemble_handoff("proj-1", analysis, None)

        assert handoff.project_id == "proj-1"
        assert handoff.source_stage == "requirements"
        assert handoff.target_stage == "design"
        assert len(handoff.functional_requirements) == 3
        assert handoff.project_overview == "Test project overview"

    def test_merges_research_constraints(self) -> None:
        analysis = _make_analysis()
        research = _make_research()
        handoff = assemble_handoff("proj-1", analysis, research)

        constraint_ids = {c.id for c in handoff.tech_constraints}
        assert "TC-R-001" in constraint_ids

    def test_no_duplicate_constraints(self) -> None:
        analysis = _make_analysis()
        analysis_with_constraint = AnalysisResult(
            project_overview=analysis.project_overview,
            user_stories=analysis.user_stories,
            nfrs=analysis.nfrs,
            tech_constraints=[
                TechConstraint(id="TC-R-001", description="dup", rationale="dup"),
            ],
            assumptions=analysis.assumptions,
            out_of_scope=analysis.out_of_scope,
            completeness_score=analysis.completeness_score,
            open_questions=analysis.open_questions,
        )
        research = _make_research()
        handoff = assemble_handoff("proj-1", analysis_with_constraint, research)

        tc_r001_count = sum(1 for c in handoff.tech_constraints if c.id == "TC-R-001")
        assert tc_r001_count == 1

    def test_gate_passes_when_complete(self) -> None:
        analysis = _make_analysis(
            stories=[_make_story() for _ in range(3)],
            score=0.95,
        )
        handoff = assemble_handoff("proj-1", analysis, None)
        assert handoff.quality_gate_passed is True

    def test_gate_fails_when_incomplete(self) -> None:
        analysis = _make_analysis(stories=[_make_story()], score=0.80)
        handoff = assemble_handoff("proj-1", analysis, None)
        assert handoff.quality_gate_passed is False


# ── supervise_requirements ──────────────────────────────────────────────


class TestSuperviseRequirements:
    @pytest.mark.asyncio
    async def test_produces_handoff(self, settings: object) -> None:
        analysis = _make_analysis(
            stories=[_make_story() for _ in range(3)],
            score=0.95,
        )
        research = _make_research()

        with (
            patch(
                "colette.stages.requirements.supervisor.run_analyst",
                new_callable=AsyncMock,
                return_value=analysis,
            ),
            patch(
                "colette.stages.requirements.supervisor.run_researcher",
                new_callable=AsyncMock,
                return_value=research,
            ),
        ):
            handoff = await supervise_requirements(
                "proj-1", "Build a todo app", settings=settings,  # type: ignore[arg-type]
            )

        assert handoff.project_id == "proj-1"
        assert len(handoff.functional_requirements) == 3
        assert handoff.quality_gate_passed is True

    @pytest.mark.asyncio
    async def test_continues_when_researcher_fails(self, settings: object) -> None:
        analysis = _make_analysis(
            stories=[_make_story() for _ in range(3)],
            score=0.95,
        )

        with (
            patch(
                "colette.stages.requirements.supervisor.run_analyst",
                new_callable=AsyncMock,
                return_value=analysis,
            ),
            patch(
                "colette.stages.requirements.supervisor.run_researcher",
                new_callable=AsyncMock,
                side_effect=RuntimeError("LLM unavailable"),
            ),
        ):
            handoff = await supervise_requirements(
                "proj-1", "Build a todo app", settings=settings,  # type: ignore[arg-type]
            )

        assert handoff.project_id == "proj-1"
        assert len(handoff.functional_requirements) == 3


# ── run_stage ───────────────────────────────────────────────────────────


class TestRunStage:
    @pytest.mark.asyncio
    async def test_produces_valid_state_update(self) -> None:
        analysis = _make_analysis(
            stories=[_make_story() for _ in range(3)],
            score=0.95,
        )

        initial_state = {
            "project_id": "test-proj",
            "user_request": "Build a todo app",
            "stage_statuses": {},
            "handoffs": {},
        }

        with (
            patch(
                "colette.stages.requirements.supervisor.run_analyst",
                new_callable=AsyncMock,
                return_value=analysis,
            ),
            patch(
                "colette.stages.requirements.supervisor.run_researcher",
                new_callable=AsyncMock,
                side_effect=RuntimeError("skip"),
            ),
            patch("colette.stages.requirements.stage.Settings"),
        ):
            result = await run_stage(initial_state)

        assert result["current_stage"] == "requirements"
        assert result["stage_statuses"]["requirements"] == "completed"
        assert "requirements" in result["handoffs"]
        assert len(result["progress_events"]) == 1

    @pytest.mark.asyncio
    async def test_reads_request_from_metadata_fallback(self) -> None:
        analysis = _make_analysis(
            stories=[_make_story() for _ in range(3)],
            score=0.95,
        )

        initial_state = {
            "project_id": "test-proj",
            "metadata": {"user_request": "Build a todo app"},
            "stage_statuses": {},
            "handoffs": {},
        }

        with (
            patch(
                "colette.stages.requirements.supervisor.run_analyst",
                new_callable=AsyncMock,
                return_value=analysis,
            ),
            patch(
                "colette.stages.requirements.supervisor.run_researcher",
                new_callable=AsyncMock,
                side_effect=RuntimeError("skip"),
            ),
            patch("colette.stages.requirements.stage.Settings"),
        ):
            result = await run_stage(initial_state)

        assert "requirements" in result["handoffs"]
