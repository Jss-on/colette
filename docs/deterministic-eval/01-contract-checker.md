# Contract Checker — OpenAPI Spec vs Implementation Diff

**Replaces**: `IntegrationTestResult.contract_tests_passed` + `contract_deviations`
**Location**: `src/colette/eval/contract_checker.py`
**Priority**: CRITICAL — this is the primary cause of rework loops

## Current Problem

The integration tester LLM receives ALL code + the entire OpenAPI spec and is asked:
"do these match?" It hallucinates deviations (e.g., "missing field: id" when the field exists),
sets `contract_tests_passed = false`, and the testing gate reworks back to design.

## Algorithm

Atomic, per-endpoint structural diff:

### Step 1: Parse OpenAPI Spec
```
Input:  DesignToImplementationHandoff.openapi_spec (JSON string)
Output: list[DeclaredEndpoint(method, path, request_fields, response_fields)]
```
- Parse JSON, iterate `paths` → each path → each method
- Extract request body field names from `requestBody.content.*.schema.properties`
- Extract response field names from `responses.2xx.content.*.schema.properties`
- Normalize paths: strip trailing slashes, lowercase methods

### Step 2: Extract Implemented Endpoints
```
Input:  list[GeneratedFile] (backend implementation files)
Output: frozenset[str] as "METHOD /path" pairs
```
Regex patterns for common frameworks:
- **FastAPI**: `@app.get("/path")`, `@router.post("/path")`
- **Express**: `app.get("/path"`, `router.post("/path"`
- **Next.js API**: filename-based routing from `app/api/` or `pages/api/`

### Step 3: Extract Tested Endpoints
```
Input:  list[GeneratedFile] (test files)
Output: frozenset[str] as "METHOD /path" pairs
```
Regex patterns:
- **httpx**: `client.get("/path")`, `client.post("/path")`
- **supertest**: `request(app).get("/path")`
- **fetch**: `fetch("/api/path", {method: "POST"}`

### Step 4: Compute Deviations (atomic per endpoint)

For each declared endpoint:
1. **Endpoint exists?** Check if `"METHOD /path"` is in implemented endpoints
   - Missing → `ContractDeviation(kind="missing_endpoint", ...)`
2. **Endpoint tested?** Check if `"METHOD /path"` is in tested endpoints
   - Missing → `ContractDeviation(kind="missing_test", ...)`
3. **Schema match?** Compare declared request/response field names against:
   - Pydantic model fields extracted from backend files (regex for `class ...Model`)
   - Mismatch → `ContractDeviation(kind="schema_mismatch", ...)`

### Step 5: Determine Pass/Fail

```python
passed = len([d for d in deviations if d.kind != "missing_test"]) == 0
```

Missing tests are informational — they don't indicate a contract violation between
design and implementation. Only missing endpoints and schema mismatches block.

## Data Types

```python
class DeclaredEndpoint(NamedTuple):
    method: str                        # "GET", "POST", etc.
    path: str                          # "/api/v1/todos"
    request_fields: frozenset[str]     # {"title", "description", "completed"}
    response_fields: frozenset[str]    # {"id", "title", "created_at"}

class ContractDeviation(NamedTuple):
    kind: str       # "missing_endpoint" | "missing_test" | "schema_mismatch"
    endpoint: str   # "GET /api/v1/todos"
    detail: str     # "Response field 'created_at' not found in TodoResponse model"

class ContractCheckResult(NamedTuple):
    passed: bool
    deviations: tuple[ContractDeviation, ...]
    endpoints_declared: int
    endpoints_implemented: int
    endpoints_tested: int
```

## Integration Point

In `stages/testing/supervisor.py`, replace `_derive_contract_passed(integration)` with:

```python
from colette.eval.contract_checker import check_contracts

contract_result = check_contracts(
    openapi_spec=state["handoffs"]["design"]["openapi_spec"],
    impl_files=generated_files,         # from pipeline state
    test_files=integration.test_files,  # from integration tester output
)
# Use contract_result.passed for gate decision
# Use contract_result.deviations for handoff.contract_deviations
```

## Edge Cases

- **Empty OpenAPI spec**: Pass (nothing to check)
- **Malformed JSON**: Pass with warning (no endpoints parseable)
- **No route decorators found**: Pass with warning (unrecognized framework)
- **Wildcard paths** (`/api/{id}`): Normalize to `/api/:id` pattern for matching

## Risk

Medium — regex extraction of route decorators may miss unusual patterns.
Mitigation: when extraction yields zero results, treat as "no data" (pass) not "zero endpoints" (fail).
