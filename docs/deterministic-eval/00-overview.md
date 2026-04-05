# Deterministic Evaluation Tools — LLM-as-Judge Elimination

## Problem

Colette's pipeline currently asks LLMs to both **generate** content AND **judge** its quality.
With weaker/free models (Qwen, Gemma), the LLM hallucinates judgments — false contract
deviations, inflated coverage estimates, phantom lint errors — triggering infinite rework loops.

**Example**: The integration tester LLM reports `contract_tests_passed: false` with fabricated
deviations, causing the testing gate to rework back to design, which re-runs implementation,
which hits the same false failure, cycling until max attempts.

## Solution

Separate generation from evaluation:

- **LLMs generate only**: code, tests, specs, finding descriptions
- **Python code evaluates**: diffs, counts, regex, AST parsing, schema validation
- **Each check is atomic**: one endpoint, one function, one pattern at a time
- **Results aggregate deterministically** into gate pass/fail decisions

## Six Locations Replaced

| # | Stage | LLM Judgment | Replacement |
|---|-------|-------------|-------------|
| 1 | Testing | `contract_tests_passed` + `contract_deviations` | `eval/contract_checker.py` — EndpointSpec diff |
| 2 | Testing | `estimated_line_coverage` + `estimated_branch_coverage` | `eval/coverage_estimator.py` — AST function coverage |
| 3 | Implementation | `lint_passed`, `type_check_passed`, `build_passed` | `eval/code_verifier.py` — syntax/import/type checks |
| 4 | Testing | `security_findings[].severity` + `.confidence` | `eval/security_patterns.py` — regex pattern matching |
| 5 | Requirements | `completeness_score` | `eval/completeness_scorer.py` — structural metrics |
| 6 | Implementation | Cross-review `findings[].severity` | `eval/cross_review_checker.py` — frontend-backend diff |

## Architecture

```
src/colette/eval/
    __init__.py
    _ast_helpers.py           # Shared AST parsing (Python via ast, TS/JS via regex)
    _pattern_registry.py      # Security anti-pattern definitions
    contract_checker.py       # OpenAPI spec vs implementation diff
    coverage_estimator.py     # AST-based test coverage estimation
    code_verifier.py          # Deterministic syntax/import/type checks
    security_patterns.py      # Regex-based security scanner
    completeness_scorer.py    # Structural requirements completeness
    cross_review_checker.py   # Frontend-backend contract diff
```

## Key Constraint

Colette generates code as `GeneratedFile` objects (path + content strings) in memory.
It does NOT execute the generated code. So we parse text/AST, not run tools.

## Documents

- [01-contract-checker.md](01-contract-checker.md) — Contract testing replacement
- [02-coverage-estimator.md](02-coverage-estimator.md) — Coverage estimation replacement
- [03-code-verifier.md](03-code-verifier.md) — Verification replacement
- [04-security-patterns.md](04-security-patterns.md) — Security scanner replacement
- [05-completeness-scorer.md](05-completeness-scorer.md) — Completeness scoring replacement
- [06-cross-review-checker.md](06-cross-review-checker.md) — Cross-review replacement
- [07-integration-plan.md](07-integration-plan.md) — Wiring into supervisors, schema changes, migration
- [08-testing-strategy.md](08-testing-strategy.md) — Test plan for the evaluators
