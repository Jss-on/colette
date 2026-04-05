"""Tests for colette.eval.completeness_scorer."""

from __future__ import annotations

from colette.eval.completeness_scorer import score_completeness


def _story(name: str, priority: str = "high", ac_count: int = 2) -> dict:
    return {
        "name": name,
        "priority": priority,
        "acceptance_criteria": [f"AC {i}" for i in range(ac_count)],
    }


def _nfr(desc: str = "Response time < 200ms") -> dict:
    return {"description": desc, "target": desc}


def _constraint(desc: str = "Use PostgreSQL") -> dict:
    return {"description": desc}


_LONG_OVERVIEW = "A comprehensive todo application with user auth and real-time updates"
_FIFTY_CHAR_OVERVIEW = "A complete project description at least fifty chars"
_MANY_FEATURES = "A comprehensive project with many features and requirements"


class TestScoreCompleteness:
    def test_full_requirements(self) -> None:
        result = score_completeness(
            project_overview=_LONG_OVERVIEW,
            user_stories=[
                _story("Create todo", "high", ac_count=3),
                _story("Delete todo", "medium", ac_count=3),
                _story("List todos", "low", ac_count=3),
                _story("Update todo", "high", ac_count=3),
                _story("Share todo", "medium", ac_count=3),
            ],
            nfrs=[_nfr("Response time < 200ms"), _nfr("99.9% uptime"), _nfr("Support 1000 users")],
            tech_constraints=[
                _constraint("Use PostgreSQL"),
                _constraint("Security: all data encrypted at rest"),
            ],
            assumptions=[{"description": "Users have internet access"}],
            out_of_scope=[{"description": "Mobile app"}],
            open_questions=[{"question": "Auth provider?"}],
        )
        assert result.final_score >= 0.85

    def test_empty_stories(self) -> None:
        result = score_completeness(
            project_overview="A project",
            user_stories=[],
            nfrs=[],
            tech_constraints=[],
            assumptions=[],
            out_of_scope=[],
            open_questions=[],
        )
        assert result.final_score <= 0.70

    def test_no_acceptance_criteria(self) -> None:
        result = score_completeness(
            project_overview=_LONG_OVERVIEW,
            user_stories=[
                {"name": "Create todo", "priority": "high", "acceptance_criteria": []},
                {"name": "Delete todo", "priority": "medium", "acceptance_criteria": []},
                {"name": "List todos", "priority": "low", "acceptance_criteria": []},
            ],
            nfrs=[_nfr()],
            tech_constraints=[_constraint()],
            assumptions=[],
            out_of_scope=[{"description": "Mobile"}],
            open_questions=[],
        )
        penalty_names = [p[0] for p in result.penalties]
        assert any("acceptance criteria" in p.lower() for p in penalty_names)

    def test_many_open_questions(self) -> None:
        result = score_completeness(
            project_overview=_LONG_OVERVIEW,
            user_stories=[_story("A", "high"), _story("B", "medium"), _story("C", "low")],
            nfrs=[_nfr()],
            tech_constraints=[_constraint()],
            assumptions=[],
            out_of_scope=[{"description": "Mobile"}],
            open_questions=[{"question": f"Q{i}"} for i in range(8)],
        )
        penalty_names = [p[0] for p in result.penalties]
        assert any("open questions" in p.lower() for p in penalty_names)

    def test_minimal_complete(self) -> None:
        result = score_completeness(
            project_overview=_FIFTY_CHAR_OVERVIEW,
            user_stories=[
                _story("A", "high", ac_count=2),
                _story("B", "medium", ac_count=2),
                _story("C", "low", ac_count=2),
            ],
            nfrs=[_nfr()],
            tech_constraints=[_constraint()],
            assumptions=[],
            out_of_scope=[{"description": "Phase 2"}],
            open_questions=[],
        )
        assert 0.75 <= result.final_score <= 1.0

    def test_detailed_stories_bonus(self) -> None:
        result = score_completeness(
            project_overview=_LONG_OVERVIEW,
            user_stories=[
                _story("A", "high", ac_count=3),
                _story("B", "medium", ac_count=4),
                _story("C", "low", ac_count=3),
            ],
            nfrs=[_nfr()],
            tech_constraints=[_constraint()],
            assumptions=[],
            out_of_scope=[{"description": "Mobile"}],
            open_questions=[],
        )
        bonus_names = [b[0] for b in result.bonuses]
        assert any("acceptance criteria" in b.lower() for b in bonus_names)

    def test_score_capped_at_one(self) -> None:
        result = score_completeness(
            project_overview=_MANY_FEATURES,
            user_stories=[
                _story("A", "high", ac_count=5),
                _story("B", "medium", ac_count=5),
                _story("C", "low", ac_count=5),
            ],
            nfrs=[_nfr("Response < 100ms"), _nfr("99.99% uptime")],
            tech_constraints=[
                _constraint("Security: encryption required"),
                _constraint("Use PostgreSQL"),
            ],
            assumptions=[{"description": "Stable internet"}],
            out_of_scope=[{"description": "Mobile app"}],
            open_questions=[],
        )
        assert result.final_score <= 1.0

    def test_score_floored_at_zero(self) -> None:
        result = score_completeness(
            project_overview="",
            user_stories=[],
            nfrs=[],
            tech_constraints=[],
            assumptions=[],
            out_of_scope=[],
            open_questions=[{"q": f"Q{i}"} for i in range(20)],
        )
        assert result.final_score >= 0.0
