# Testing Strategy for Deterministic Evaluators

## Test Structure

```
tests/unit/eval/
    __init__.py
    test_ast_helpers.py
    test_contract_checker.py
    test_coverage_estimator.py
    test_code_verifier.py
    test_security_patterns.py
    test_completeness_scorer.py
    test_cross_review_checker.py
```

## Test Cases per Module

### test_ast_helpers.py

| Test | Input | Expected |
|------|-------|----------|
| Parse valid Python | `def foo(): pass` | 1 function, name="foo" |
| Parse Python class | `class User: def save(self): ...` | 1 class, 1 method |
| Parse Python imports | `from app.models import User` | 1 import, module="app.models" |
| Parse valid TypeScript | `export function getTodos() {}` | 1 function, name="getTodos" |
| Parse malformed content | `def foo(` (unterminated) | Returns None |
| Count Python branches | `if x: ... elif y: ... else: ...` | 3 branches |
| Count TS branches | `if (x) {} else if (y) {} else {}` | 3 branches |
| Extract exported names | `__all__ = ["User", "Todo"]` | {"User", "Todo"} |

### test_contract_checker.py

| Test | Input | Expected |
|------|-------|----------|
| All endpoints match | 3 spec endpoints, 3 impl routes | passed=True, 0 deviations |
| Missing endpoint | 3 spec, 2 impl routes | 1 "missing_endpoint" deviation |
| Schema mismatch | Spec field "email", impl field "mail" | 1 "schema_mismatch" deviation |
| Missing test | 3 impl, 2 tested | 1 "missing_test" (non-blocking) |
| Empty spec | "" | passed=True (nothing to check) |
| Malformed JSON | "{invalid" | passed=True with warning |
| Path normalization | `/api/users/` vs `/api/users` | Match |

### test_coverage_estimator.py

| Test | Input | Expected |
|------|-------|----------|
| Full coverage | 5 source funcs, all in tests | ~100% line |
| Partial coverage | 5 source funcs, 3 in tests | ~60% line |
| No test files | 5 source funcs, 0 tests | 0% |
| No source funcs | Config files only | 100% |
| Branch coverage | 4 branches in covered funcs, 2 uncovered | ~67% branch |
| Wrong name reference | Test calls `get_user`, source has `get_users` | Not covered |

### test_code_verifier.py

| Test | Input | Expected |
|------|-------|----------|
| Valid Python | Syntactically correct file | lint_passed=True |
| Syntax error | `def foo(` | lint_passed=False |
| Valid imports | `from app.models import User` + `app/models.py` in set | build_passed=True |
| Missing import | `from app.missing import X` | build_passed=False |
| Stdlib import | `import os` | No finding (known stdlib) |
| Missing return type | `def foo():` (public) | type_check_passed=False |
| Private function | `def _foo():` (no annotation) | No finding |
| Missing __init__.py | `from app.utils import X` without `app/__init__.py` | Finding |
| TS unbalanced braces | `function foo() {` | lint_passed=False |

### test_security_patterns.py

| Test | Input | Expected |
|------|-------|----------|
| SQL f-string | `execute(f"SELECT ...")` | CRITICAL SEC-SQL-001 |
| SQL parameterized | `execute("SELECT ...", (id,))` | No match |
| Hardcoded secret | `api_key = "sk-1234abcd..."` | CRITICAL SEC-CRED-001 |
| Env var secret | `api_key = os.environ["KEY"]` | Suppressed (negative pattern) |
| Test secret | `password = "test_password"` | Suppressed (negative pattern) |
| XSS danger | `dangerouslySetInnerHTML` | HIGH SEC-XSS-001 |
| XSS sanitized | `DOMPurify.sanitize(...) + dangerouslySetInnerHTML` | Suppressed |
| Consolidation | Same pattern in 5 files | 1 consolidated finding |
| Empty files | [] | Empty report |

### test_completeness_scorer.py

| Test | Input | Expected |
|------|-------|----------|
| Full requirements | 5 stories, 3 NFRs, constraints, out-of-scope | >= 0.85 |
| Empty stories | 0 stories | <= 0.70 |
| No acceptance criteria | 3 stories, no AC | penalty applied |
| Many open questions | 8 open questions | penalty (-0.06) |
| Minimal complete | 3 stories with AC, 1 NFR | ~0.80 |
| Bonus: detailed stories | Stories with >= 3 AC each | +0.05 bonus |

### test_cross_review_checker.py

| Test | Input | Expected |
|------|-------|----------|
| Matching endpoints | Frontend `GET /api/todos`, backend `GET /api/todos` | No findings |
| Missing backend | Frontend calls `GET /api/users`, backend missing | CRITICAL finding |
| Unused backend | Backend `GET /api/health`, frontend doesn't call | MEDIUM finding |
| Field mismatch | Frontend sends `{name}`, backend expects `{username}` | HIGH finding |
| Case normalization | `created_at` vs `createdAt` | Match (normalized) |
| No frontend files | Backend only | Empty report |

## Modified Existing Tests

| File | Changes |
|------|---------|
| `tests/unit/stages/test_testing_stage.py` | Remove LLM coverage/contract fixtures; verify deterministic flow |
| `tests/unit/stages/test_verifier.py` | Test deterministic verification instead of LLM mock |
| `tests/unit/stages/test_implementation_stage.py` | Update cross-review assertions |
| `tests/unit/stages/test_requirements_stage.py` | Update completeness score assertions |
| `tests/unit/gates/test_gates.py` | No changes (gates consume same fields) |

## Coverage Target

All new `eval/` modules: >= 90% coverage (these are critical infrastructure).
Modified supervisor/stage files: maintain existing >= 80%.
