# Coverage Estimator — AST-Based Test Coverage

**Replaces**: `UnitTestResult.estimated_line_coverage` + `estimated_branch_coverage`
**Location**: `src/colette/eval/coverage_estimator.py`
**Priority**: HIGH — these values gate at 80%/70% thresholds

## Current Problem

The LLM guesses coverage at 85-90% regardless of actual test quality. A pipeline with
3 test stubs and 50 implementation functions gets "88% coverage" because the LLM
optimistically self-rates.

## Algorithm

### Line Coverage Estimation

```
function_coverage = (source functions referenced in tests / total source functions) * 100
```

1. Parse all source files (non-test) → extract function/method names
2. Parse all test files → extract all names referenced (imports, function calls, assertions)
3. A source function is "covered" if its name appears in the test target set
4. This is conservative: it undercounts indirect coverage (helper functions called by tested code)

### Branch Coverage Estimation

```
branch_coverage = (branches in covered functions / total branches) * 100
```

1. Count branch points per function: `if`, `elif`, `else`, `for`, `while`, `except`, ternary
2. If a function is "covered" (by the line coverage check), all its branches count as covered
3. This is a coarse estimate — real branch coverage requires execution

### Configurable Boost Factor

Since structural analysis underestimates real coverage, apply a configurable multiplier:

```python
adjusted_line = min(raw_line * settings.coverage_estimation_multiplier, 100.0)
adjusted_branch = min(raw_branch * settings.coverage_estimation_multiplier, 100.0)
```

Default multiplier: `1.15` (reflecting that tests exercise code indirectly).

## Data Types

```python
class CoverageEstimate(NamedTuple):
    line_coverage: float      # 0.0 - 100.0
    branch_coverage: float    # 0.0 - 100.0
    functions_total: int
    functions_covered: int
    branches_total: int
    branches_covered: int
```

## Integration Point

In `stages/testing/supervisor.py`, replace `_compute_coverage`:

```python
def _compute_coverage(source_files, test_files):
    from colette.eval.coverage_estimator import estimate_coverage
    result = estimate_coverage(source_files, test_files)
    return result.line_coverage, result.branch_coverage
```

## Edge Cases

- **No source functions** (config files only): 100% coverage (nothing to test)
- **No test files**: 0% coverage
- **Source function called `test_*`**: Exclude from source set (it's a test)
- **Duplicate function names** across files: Count each file's function independently
