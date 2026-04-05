"""Deterministic frontend vs backend contract diff.

Replaces LLM cross-review ``CrossReviewResult.findings[].severity``.
"""

from __future__ import annotations

import re
from typing import NamedTuple

# ── Data types ───────────────────────────────────────────────────────


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


# ── Extraction helpers ───────────────────────────────────────────────

_FETCH_PATTERN = re.compile(r"""(?:fetch|axios\.?\w*|api\.?\w*)\s*\(\s*[`"']([^`"']+)[`"']""")
_FETCH_METHOD = re.compile(r"""(?:fetch|axios)\s*\.\s*(get|post|put|patch|delete)\s*\(""")
_BACKEND_ROUTE = re.compile(
    r"""@(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["']([^"']+)["']"""
)
_EXPRESS_ROUTE = re.compile(
    r"""(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["']([^"']+)["']"""
)


def _normalize_field_name(name: str) -> str:
    """Convert camelCase/snake_case to common lowercase form."""
    # camelCase to snake_case
    result = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    return result.lower().strip("_")


def _extract_frontend_api_calls(
    files: list[dict[str, str]],
) -> dict[str, frozenset[str]]:
    """Extract endpoint -> request field names from frontend files."""
    endpoints: dict[str, set[str]] = {}
    for f in files:
        content = f.get("content", "")
        for match in _FETCH_PATTERN.finditer(content):
            path = match.group(1)
            if path.startswith("/") or path.startswith("http"):
                # Normalize to just the path portion
                path = re.sub(r"https?://[^/]+", "", path)
                path = path.split("?")[0].rstrip("/") or "/"
                endpoints.setdefault(path, set())

    return {k: frozenset(v) for k, v in endpoints.items()}


def _extract_backend_routes(
    files: list[dict[str, str]],
) -> dict[str, frozenset[str]]:
    """Extract endpoint -> response field names from backend files."""
    endpoints: dict[str, set[str]] = {}
    for f in files:
        content = f.get("content", "")
        for pattern in (_BACKEND_ROUTE, _EXPRESS_ROUTE):
            for match in pattern.finditer(content):
                method = match.group(1).upper()
                path = match.group(2).rstrip("/") or "/"
                key = f"{method} {path}"
                endpoints.setdefault(key, set())

    return {k: frozenset(v) for k, v in endpoints.items()}


# ── Main entry ───────────────────────────────────────────────────────


def check_cross_review(
    frontend_files: list[dict[str, str]],
    backend_files: list[dict[str, str]],
) -> CrossReviewReport:
    """Compare frontend API calls against backend route definitions."""
    if not frontend_files:
        return CrossReviewReport(
            findings=(),
            frontend_endpoints_called=0,
            backend_endpoints_defined=0,
            has_critical=False,
        )

    fe_calls = _extract_frontend_api_calls(frontend_files)
    be_routes = _extract_backend_routes(backend_files)

    if not be_routes:
        return CrossReviewReport(
            findings=(),
            frontend_endpoints_called=len(fe_calls),
            backend_endpoints_defined=0,
            has_critical=False,
        )

    # Normalize backend paths for comparison
    be_paths: set[str] = set()
    for key in be_routes:
        parts = key.split(" ", 1)
        if len(parts) == 2:
            be_paths.add(parts[1])

    findings: list[CrossReviewFinding] = []

    # Frontend calls endpoint not in backend
    for fe_path in fe_calls:
        normalized = fe_path.rstrip("/") or "/"
        if normalized not in be_paths:
            findings.append(
                CrossReviewFinding(
                    severity="CRITICAL",
                    category="missing_backend_endpoint",
                    description=(f"Frontend calls '{fe_path}' but no backend route defined"),
                    frontend_location=fe_path,
                    backend_location="",
                )
            )

    # Backend endpoint not called by frontend
    for be_path in be_paths:
        if be_path not in fe_calls:
            findings.append(
                CrossReviewFinding(
                    severity="MEDIUM",
                    category="unused_endpoint",
                    description=(f"Backend defines '{be_path}' but frontend never calls it"),
                    frontend_location="",
                    backend_location=be_path,
                )
            )

    has_critical = any(f.severity == "CRITICAL" for f in findings)

    return CrossReviewReport(
        findings=tuple(findings),
        frontend_endpoints_called=len(fe_calls),
        backend_endpoints_defined=len(be_routes),
        has_critical=has_critical,
    )
