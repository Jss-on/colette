"""Security anti-pattern definitions for deterministic scanning."""

from __future__ import annotations

from typing import NamedTuple


class SecurityPattern(NamedTuple):
    id: str
    category: str
    severity: str
    pattern: str
    description: str
    recommendation: str
    languages: frozenset[str]
    negative_pattern: str | None


SECURITY_PATTERNS: tuple[SecurityPattern, ...] = (
    SecurityPattern(
        id="SEC-SQL-001",
        category="sql_injection",
        severity="CRITICAL",
        pattern=r'(?:execute|query|raw)\s*\(\s*f["\']',
        description="SQL query using f-string interpolation",
        recommendation="Use parameterized queries instead of f-strings",
        languages=frozenset({"python"}),
        negative_pattern=None,
    ),
    SecurityPattern(
        id="SEC-SQL-002",
        category="sql_injection",
        severity="CRITICAL",
        pattern=r"(?:execute|query)\s*\(.*?\+",
        description="SQL query using string concatenation",
        recommendation="Use parameterized queries instead of string concatenation",
        languages=frozenset({"python", "typescript"}),
        negative_pattern=None,
    ),
    SecurityPattern(
        id="SEC-CRED-001",
        category="hardcoded_credential",
        severity="CRITICAL",
        pattern=r'(?:password|secret|api_key|apikey|api_secret)\s*=\s*["\'][^"\']{4,}["\']',
        description="Hardcoded credential or secret",
        recommendation="Use environment variables or a secret manager",
        languages=frozenset({"python", "typescript"}),
        negative_pattern=r"os\.environ|process\.env|test|mock|fake|example|placeholder|xxx|changeme",
    ),
    SecurityPattern(
        id="SEC-XSS-001",
        category="xss",
        severity="HIGH",
        pattern=r"dangerouslySetInnerHTML",
        description="Use of dangerouslySetInnerHTML without sanitization",
        recommendation="Sanitize HTML with DOMPurify before rendering",
        languages=frozenset({"typescript"}),
        negative_pattern=r"sanitize|DOMPurify|dompurify",
    ),
    SecurityPattern(
        id="SEC-PATH-001",
        category="path_traversal",
        severity="HIGH",
        pattern=r"(?:open|readFile|writeFile|readFileSync|writeFileSync)\s*\(.*?(?:req\.|params\.|query\.)",
        description="File operation using unsanitized request parameter",
        recommendation="Validate and sanitize file paths; use an allowlist",
        languages=frozenset({"python", "typescript"}),
        negative_pattern=r"sanitize|validate|allowlist",
    ),
    SecurityPattern(
        id="SEC-EVAL-001",
        category="code_injection",
        severity="CRITICAL",
        pattern=r"\beval\s*\(",
        description="Use of eval() with potential user input",
        recommendation="Use ast.literal_eval or a safe parser instead",
        languages=frozenset({"python", "typescript"}),
        negative_pattern=r"ast\.literal_eval|literal_eval",
    ),
    SecurityPattern(
        id="SEC-CSRF-001",
        category="csrf",
        severity="MEDIUM",
        pattern=r"@(?:app|router)\.(?:post|put|delete)\s*\(",
        description="State-changing endpoint without CSRF protection",
        recommendation="Add CSRF token validation middleware",
        languages=frozenset({"python"}),
        negative_pattern=r"csrf_token|csrfmiddleware|CSRFMiddleware|csrf_protect",
    ),
    SecurityPattern(
        id="SEC-CORS-001",
        category="cors",
        severity="MEDIUM",
        pattern=r'Access-Control-Allow-Origin["\s:]*\*',
        description="Wildcard CORS origin allows any domain",
        recommendation="Restrict CORS to specific trusted origins",
        languages=frozenset({"python", "typescript"}),
        negative_pattern=None,
    ),
    SecurityPattern(
        id="SEC-AUTH-001",
        category="auth_bypass",
        severity="HIGH",
        pattern=r"@(?:app|router)\.(?:get|post|put|delete)\s*\(",
        description="Route handler without authentication decorator",
        recommendation="Add @login_required or Depends(get_current_user)",
        languages=frozenset({"python"}),
        negative_pattern=r"@login_required|Depends\(get_current_user\)|@public|@no_auth|/health|/docs|/openapi",
    ),
)
