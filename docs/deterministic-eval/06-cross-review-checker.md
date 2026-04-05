# Cross-Review Checker — Frontend vs Backend Contract Diff

**Replaces**: LLM cross-review `CrossReviewResult.findings[].severity`
**Location**: `src/colette/eval/cross_review_checker.py`
**Priority**: MEDIUM — CRITICAL findings block the implementation gate

## Current Problem

The LLM cross-review assigns arbitrary severity to findings. With weak models, it either
hallucinates "API contract mismatch" for endpoints that match perfectly, or produces
empty results (0-byte response) requiring retries.

## Algorithm

### Step 1: Extract Frontend API Calls

Regex patterns for common frontend HTTP clients:

```
fetch("/api/users", { method: "POST", body: JSON.stringify({ name, email }) })
axios.get("/api/users")
api.post("/api/todos", { title, description })
```

Extract: `{endpoint_key: request_field_names}`

### Step 2: Extract Backend Route Handlers

```
@app.post("/api/users")
async def create_user(user: UserCreate):
    ...
    return UserResponse(id=..., name=..., email=...)

router.get("/api/users")
```

Extract: `{endpoint_key: response_field_names}`

### Step 3: Diff (atomic per endpoint)

| Condition | Severity | Category |
|-----------|----------|----------|
| Frontend calls endpoint not in backend | **CRITICAL** | missing_backend_endpoint |
| Backend defines endpoint not called by frontend | **MEDIUM** | unused_endpoint |
| Request field names differ (frontend sends field backend doesn't accept) | **HIGH** | request_mismatch |
| Response field consumed by frontend not in backend response model | **HIGH** | response_mismatch |

Severity is **deterministic** based on the diff type, not LLM judgment.

## Data Types

```python
class CrossReviewFinding(NamedTuple):
    severity: str
    category: str
    description: str
    frontend_location: str
    backend_location: str

class CrossReviewReport(NamedTuple):
    findings: tuple[CrossReviewFinding, ...]
    frontend_endpoints_called: int
    backend_endpoints_defined: int
    has_critical: bool
```

## Integration Point

In `stages/implementation/supervisor.py`, replace `_run_cross_review`:

```python
def _run_cross_review_deterministic(frontend, backend):
    from colette.eval.cross_review_checker import check_cross_review
    report = check_cross_review(frontend.files, backend.files)
    return CrossReviewResult(
        findings=[ReviewFinding(severity=f.severity, ...) for f in report.findings],
        summary=f"Checked {report.frontend_endpoints_called} calls vs {report.backend_endpoints_defined} routes.",
    )
```

This is now **synchronous** (no LLM call), simplifying error handling.

## Edge Cases

- **No frontend files**: Skip check, return empty report (backend-only project)
- **No route patterns found**: Skip check, return empty report (unrecognized framework)
- **camelCase vs snake_case**: Normalize field names before comparison (`created_at` = `createdAt`)
