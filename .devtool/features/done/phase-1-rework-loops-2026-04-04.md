---
id: "phase-1-rework-loops-2026-04-04"
status: "done"
priority: "critical"
assignee: "claude"
dueDate: "2026-04-04"
created: "2026-04-04T00:00:00Z"
modified: "2026-04-03T18:56:56.876Z"
completedAt: null
labels: ["phase", "phase-1"]
order: "a0"
---
# Phase 1: Rework Loops (Foundation)

## Goal
Gate failure triggers rework instead of pipeline termination. Gates return ternary results: pass | rework_self | rework_target(stage_name).

## Tasks
- [x] Create src/colette/schemas/rework.py (ReworkDirective, ReworkDecision)
- [x] Modify orchestrator/state.py (add rework fields)
- [x] Modify config.py (add rework settings)
- [x] Create orchestrator/rework_router.py (ReworkRouter class)
- [x] Modify gates/base.py (QualityGateResult rework fields)
- [x] Update all 5 gate files for rework decisions
- [x] Modify pipeline.py for backward edges
- [x] Update stage supervisors for rework context
- [x] Write tests (53 tests, 100% coverage on new code)
- [x] make check (lint + typecheck clean, all tests pass)
- [x] git commit and push

## Notes
- Overall coverage 79.26% is pre-existing, new code has 100% coverage
- Rework context centralized in pipeline.py stage wrapper; Phase 2 adds FeedbackAugmenter
