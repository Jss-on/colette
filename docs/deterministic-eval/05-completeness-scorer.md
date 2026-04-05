# Completeness Scorer — Structural Requirements Scoring

**Replaces**: `AnalysisResult.completeness_score` (LLM self-assessment)
**Location**: `src/colette/eval/completeness_scorer.py`
**Priority**: MEDIUM — blocks gate at 0.80

## Current Problem

The LLM self-rates completeness between 0.85-0.95 regardless of actual content quality.
The supervisor applies penalties, but starting from a hallucinated base score means the
final score is unreliable. A near-empty PRD with 1 vague user story gets 0.82.

## Algorithm

Start at `1.0`, apply structural penalties and bonuses:

### Penalties

| Condition | Penalty | Rationale |
|-----------|---------|-----------|
| No user stories | -0.30 | Core deliverable missing |
| < 3 user stories | -0.10 | Underspecified scope |
| No NFRs | -0.10 | Non-functional requirements missing |
| Stories without acceptance criteria | -0.10 | Untestable requirements |
| > 5 open questions | -0.02 each (max -0.08) | Too many unknowns |
| No tech constraints | -0.05 | No technical guidance |
| Project overview < 50 chars | -0.10 | Description too vague |
| All stories same priority | -0.05 | No prioritization |
| No out-of-scope section | -0.05 | Scope boundaries unclear |

### Bonuses (capped so total <= 1.0)

| Condition | Bonus | Rationale |
|-----------|-------|-----------|
| Stories with >= 3 acceptance criteria each | +0.05 | Well-specified |
| NFRs with measurable targets | +0.05 | Quantified quality |
| Security/compliance constraints present | +0.05 | Explicitly addressed |

### Formula

```python
final_score = max(0.0, min(1.0, 1.0 - sum(penalties) + sum(bonuses)))
```

## Data Types

```python
class CompletenessBreakdown(NamedTuple):
    base_score: float                            # always 1.0
    penalties: tuple[tuple[str, float], ...]      # (reason, amount)
    bonuses: tuple[tuple[str, float], ...]
    final_score: float
```

## Integration Point

In `stages/requirements/supervisor.py`, replace `_compute_completeness`:

```python
def _compute_completeness(analysis: AnalysisResult) -> float:
    from colette.eval.completeness_scorer import score_completeness
    breakdown = score_completeness(
        project_overview=analysis.project_overview,
        user_stories=analysis.user_stories,
        nfrs=analysis.nfrs,
        tech_constraints=analysis.tech_constraints,
        assumptions=analysis.assumptions,
        out_of_scope=analysis.out_of_scope,
        open_questions=analysis.open_questions,
    )
    return breakdown.final_score
```

The existing supervisor penalty logic is **subsumed** by the new scorer (same penalties + more).
Remove `completeness_score` from the `AnalysisResult` Pydantic model and from the analyst prompt.
