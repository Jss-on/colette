# Integration Plan — Wiring Evaluators into the Pipeline

## Implementation Phases

### Phase 1: Foundation (No pipeline changes)
- Create `src/colette/eval/__init__.py`
- Create `src/colette/eval/_ast_helpers.py` — shared AST parsing
- Write tests for `_ast_helpers`
- **Risk**: Low

### Phase 2: Contract Checker (Location 1)
- Create `src/colette/eval/contract_checker.py`
- Write tests
- **Risk**: Medium (regex extraction is framework-dependent)

### Phase 3: Coverage Estimator (Location 2)
- Create `src/colette/eval/coverage_estimator.py`
- Write tests
- **Risk**: Medium (structural estimation underestimates)

### Phase 4: Code Verifier (Location 3)
- Create `src/colette/eval/code_verifier.py`
- Write tests
- **Risk**: Low (Python ast module is reliable)

### Phase 5: Security Patterns (Location 4)
- Create `src/colette/eval/_pattern_registry.py`
- Create `src/colette/eval/security_patterns.py`
- Write tests
- **Risk**: Low (regex patterns are well-understood)

### Phase 6: Completeness Scorer (Location 5)
- Create `src/colette/eval/completeness_scorer.py`
- Write tests
- **Risk**: Low (pure arithmetic on existing types)

### Phase 7: Cross-Review Checker (Location 6)
- Create `src/colette/eval/cross_review_checker.py`
- Write tests
- **Risk**: Medium (framework-dependent regex)

### Phase 8: Integration (Pipeline changes)
**This is the critical phase.** Wire evaluators into existing supervisors.

| Step | File Modified | Change |
|------|--------------|--------|
| 8.1 | `stages/testing/integration_tester.py` | Remove `contract_tests_passed` + `contract_deviations` from LLM output model |
| 8.2 | `stages/testing/unit_tester.py` | Remove `estimated_line_coverage` + `estimated_branch_coverage` from LLM output model |
| 8.3 | `stages/testing/supervisor.py` | Wire contract_checker + coverage_estimator; accept `source_files` param |
| 8.4 | `stages/testing/security_scanner.py` | Add deterministic severity override merge |
| 8.5 | `stages/implementation/verifier.py` | Replace LLM verify with `code_verifier.verify_files` |
| 8.6 | `stages/implementation/supervisor.py` | Replace LLM cross-review with `cross_review_checker` |
| 8.7 | `stages/requirements/analyst.py` | Remove `completeness_score` from `AnalysisResult` |
| 8.8 | `stages/requirements/supervisor.py` | Wire completeness_scorer |

### Phase 9: Schema Adjustments
- Verify handoff field compatibility (same names, same types)
- Add `generated_files` to `PipelineState` in `orchestrator/state.py`
- Gates require NO modification

### Phase 10: Prompt Updates
- Remove judgment instructions from all affected prompts
- LLMs still generate content; they just don't rate it

## Modified Files Summary

### New files (9):
| File | Purpose |
|------|---------|
| `src/colette/eval/__init__.py` | Package init |
| `src/colette/eval/_ast_helpers.py` | Shared AST parsing |
| `src/colette/eval/_pattern_registry.py` | Security anti-pattern definitions |
| `src/colette/eval/contract_checker.py` | OpenAPI spec vs implementation diff |
| `src/colette/eval/coverage_estimator.py` | AST-based test coverage estimation |
| `src/colette/eval/code_verifier.py` | Deterministic syntax/import/type checks |
| `src/colette/eval/security_patterns.py` | Regex-based security scanner |
| `src/colette/eval/completeness_scorer.py` | Structural requirements completeness |
| `src/colette/eval/cross_review_checker.py` | Frontend-backend contract diff |

### Modified files (12):
| File | Change |
|------|--------|
| `stages/testing/integration_tester.py` | Remove LLM judgment fields |
| `stages/testing/unit_tester.py` | Remove LLM coverage estimates |
| `stages/testing/security_scanner.py` | Add deterministic severity merge |
| `stages/testing/supervisor.py` | Wire in evaluators |
| `stages/testing/prompts.py` | Remove judgment instructions |
| `stages/implementation/verifier.py` | Replace LLM verify |
| `stages/implementation/supervisor.py` | Replace LLM cross-review |
| `stages/implementation/prompts.py` | Deprecate verification/cross-review prompts |
| `stages/requirements/analyst.py` | Remove completeness_score |
| `stages/requirements/supervisor.py` | Wire completeness scorer |
| `stages/requirements/prompts.py` | Remove completeness instructions |
| `orchestrator/state.py` | Add `generated_files` to PipelineState |

### Unmodified files (gates):
| File | Reason |
|------|--------|
| `gates/requirements_gate.py` | Reads same `completeness_score` field |
| `gates/implementation_gate.py` | Reads same `lint_passed` etc fields |
| `gates/testing_gate.py` | Reads same `overall_line_coverage` etc fields |

## Migration Strategy

### Feature Flag

```python
# config.py
use_deterministic_eval: bool = Field(
    default=False,
    description="Use deterministic evaluators instead of LLM-as-judge.",
)
```

When `False`: existing LLM-based evaluation (current behavior).
When `True`: new deterministic evaluators.

This allows gradual rollout and easy rollback.

### Backward Compatibility

- Handoff schemas keep the same field names and types
- Gates consume the same fields — zero gate changes needed
- Add `model_config = {"extra": "ignore"}` to agent result models for checkpoint compatibility
- Keep old LLM functions renamed with `_llm` suffix as fallback

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| AST coverage underestimates | Configurable boost multiplier (default 1.15) |
| Regex misses framework patterns | Zero results → skip check (pass), not fail |
| Breaking serialized checkpoints | `extra = "ignore"` on affected models |
| Large migration | Feature flag for rollback |
| Security false negatives | LLM scanner runs in parallel as advisory |
