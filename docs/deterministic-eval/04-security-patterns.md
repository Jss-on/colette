# Security Pattern Scanner — Regex-Based Detection

**Replaces**: `SecurityScanResult.findings[].severity` + `.confidence` (LLM-assigned)
**Location**: `src/colette/eval/security_patterns.py` + `_pattern_registry.py`
**Priority**: HIGH — CRITICAL/HIGH findings block the gate

## Current Problem

The LLM assigns arbitrary severity and confidence levels to security findings.
A free model might flag `os.environ["API_KEY"]` as CRITICAL (it's actually safe)
or miss `execute(f"SELECT * FROM users WHERE id={user_id}")` entirely.

## Architecture

Two files:
- `_pattern_registry.py` — Pattern definitions (data, not logic)
- `security_patterns.py` — Matching engine

### Pattern Structure

```python
class SecurityPattern(NamedTuple):
    id: str                           # "SEC-SQL-001"
    category: str                     # "sql_injection"
    severity: str                     # "CRITICAL"
    pattern: str                      # regex
    description: str                  # human-readable
    recommendation: str               # fix suggestion
    languages: frozenset[str]         # {"python", "typescript"}
    negative_pattern: str | None      # regex that suppresses false positive
```

### Pattern Registry

| ID | Category | Severity | Pattern | Negative Pattern |
|----|----------|----------|---------|-----------------|
| SEC-SQL-001 | sql_injection | CRITICAL | `execute\|query\|raw` + f-string | — |
| SEC-SQL-002 | sql_injection | CRITICAL | `execute\|query` + string concat | — |
| SEC-CRED-001 | hardcoded_credential | CRITICAL | `password\|secret\|api_key = "..."` | `os.environ\|process.env\|test\|mock\|fake\|example` |
| SEC-XSS-001 | xss | HIGH | `dangerouslySetInnerHTML` | `sanitize\|DOMPurify` |
| SEC-PATH-001 | path_traversal | HIGH | file ops with `req.\|params.\|query.` | `sanitize\|validate\|allowlist` |
| SEC-EVAL-001 | code_injection | CRITICAL | `eval(` with user input | `ast.literal_eval` |
| SEC-CSRF-001 | csrf | MEDIUM | POST/PUT/DELETE without CSRF token | `csrf_token\|csrfmiddleware` |
| SEC-CORS-001 | cors | MEDIUM | `Access-Control-Allow-Origin: *` | — |
| SEC-AUTH-001 | auth_bypass | HIGH | route without auth decorator | `@login_required\|Depends(get_current_user)` |

### Matching Algorithm (per file, per pattern)

```
for each line in file:
    if pattern matches line AND file language in pattern.languages:
        if negative_pattern exists AND negative_pattern matches same line:
            suppress (false positive)
        else:
            emit PatternMatch
```

### Consolidation

Multiple matches of the same pattern across files → one finding with a list of locations.
"5 endpoints missing rate limiting" is ONE finding, not five.

## Data Types

```python
class PatternMatch(NamedTuple):
    pattern_id: str
    category: str
    severity: str
    file_path: str
    line: int
    matched_text: str
    description: str
    recommendation: str

class SecurityScanReport(NamedTuple):
    matches: tuple[PatternMatch, ...]
    has_blocking: bool          # any CRITICAL or HIGH
    patterns_checked: int
    files_scanned: int
```

## Integration Point

In `stages/testing/security_scanner.py`:

```python
# LLM still runs (for finding descriptions/recommendations)
llm_result = await invoke_structured(...)

# Deterministic scan runs independently
from colette.eval.security_patterns import scan_files
det_result = scan_files(impl_files)

# Merge: deterministic severity overrides LLM severity
merged = _merge_with_deterministic(llm_result, det_result)
```

LLM findings that match a deterministic pattern → keep deterministic severity.
LLM findings with no deterministic match → downgrade to INFO (advisory only).
Deterministic findings not in LLM output → add as new findings.
