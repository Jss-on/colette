# Code Verifier — Deterministic Syntax/Import/Type Checks

**Replaces**: `VerificationReport` from LLM verifier (lint_passed, type_check_passed, build_passed)
**Location**: `src/colette/eval/code_verifier.py`
**Priority**: MEDIUM — currently advisory only, but feeds into the verify-fix loop

## Current Problem

The LLM verifier hallucinates errors (e.g., "undefined variable db_session" when the import
exists 3 lines above), triggering fix loops that waste tokens and time. It also misses real
syntax errors because it doesn't actually parse the code.

## Algorithm (per file)

### 1. Syntax Check → `lint_passed`

**Python**: `ast.parse(content)` — authoritative, zero false positives
**TypeScript/JS**: Check balanced braces `{}`, brackets `[]`, parentheses `()`

### 2. Import Consistency → `build_passed`

For each import in file A:
- Is the imported module in the generated file set? (e.g., `from app.models import User` → is `app/models.py` present?)
- Is it a known stdlib module? (use `sys.stdlib_module_names` for Python)
- Is it a known third-party package? (check against a list of common packages: `fastapi`, `pydantic`, `react`, `express`, etc.)
- Unknown import → finding (severity: HIGH if used in function body, MEDIUM otherwise)

### 3. Type Annotation Presence → `type_check_passed`

For Python files:
- Public functions (not `_prefixed`) must have return type annotations
- Missing annotation → finding (severity: LOW)

For TypeScript files:
- Functions with `export` must have return type or use inference
- `any` type usage → finding (severity: MEDIUM)

### 4. Package Structure

- Python: verify `__init__.py` exists for packages implied by import paths
- Missing → finding (severity: HIGH, category: "structure")

## Data Types

```python
class VerificationFinding(NamedTuple):
    category: str       # "syntax" | "import" | "type" | "structure"
    severity: str       # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    file_path: str
    line: int | None
    message: str

class DeterministicVerificationReport(NamedTuple):
    findings: tuple[VerificationFinding, ...]
    lint_passed: bool       # no syntax errors
    type_check_passed: bool # all public functions have type annotations
    build_passed: bool      # all imports resolve
```

## Integration Point

In `stages/implementation/verifier.py`, replace the LLM call:

```python
from colette.eval.code_verifier import verify_files

all_files = [*frontend.files, *backend.files, *database.files]
report = verify_files(all_files)  # deterministic, no LLM

if report.lint_passed and report.build_passed:
    return frontend, backend, database, report

# Fix loop: LLM fixes, then re-verify deterministically
```

## Known Third-Party Packages

Maintain a frozen set of common packages the LLM may use:

```python
KNOWN_PACKAGES = frozenset({
    # Python
    "fastapi", "pydantic", "sqlalchemy", "alembic", "pytest", "httpx",
    "uvicorn", "redis", "celery", "jwt", "bcrypt", "passlib",
    # Node/TS
    "react", "next", "express", "prisma", "zod", "axios", "jest",
    "tailwindcss", "lucide-react", "shadcn",
})
```

This list is extensible via settings.
