"""Deterministic OpenAPI spec vs implementation diff.

Replaces ``IntegrationTestResult.contract_tests_passed`` +
``contract_deviations`` with structural comparison.
"""

from __future__ import annotations

import json
import re
from typing import NamedTuple

# ── Data types ───────────────────────────────────────────────────────


class DeclaredEndpoint(NamedTuple):
    method: str
    path: str
    request_fields: frozenset[str]
    response_fields: frozenset[str]


class ContractDeviation(NamedTuple):
    kind: str  # "missing_endpoint" | "missing_test" | "schema_mismatch"
    endpoint: str  # "GET /api/v1/todos"
    detail: str


class ContractCheckResult(NamedTuple):
    passed: bool
    deviations: tuple[ContractDeviation, ...]
    endpoints_declared: int
    endpoints_implemented: int
    endpoints_tested: int


# ── Parsing ──────────────────────────────────────────────────────────


def _normalize_path(path: str) -> str:
    """Strip trailing slash and normalize ``{id}`` to ``:id``."""
    path = path.rstrip("/") or "/"
    path = re.sub(r"\{(\w+)\}", r":\1", path)
    return path.lower()


def parse_openapi_spec(spec_json: str) -> list[DeclaredEndpoint]:
    """Parse an OpenAPI JSON string into declared endpoints."""
    try:
        spec = json.loads(spec_json)
    except (json.JSONDecodeError, TypeError):
        return []

    paths = spec.get("paths", {})
    endpoints: list[DeclaredEndpoint] = []

    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        norm_path = _normalize_path(path)
        for method, details in methods.items():
            method_upper = method.upper()
            if method_upper not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                continue
            if not isinstance(details, dict):
                continue

            request_fields = _extract_schema_fields(details.get("requestBody", {}))
            response_fields = _extract_response_fields(details.get("responses", {}))

            endpoints.append(
                DeclaredEndpoint(
                    method=method_upper,
                    path=norm_path,
                    request_fields=frozenset(request_fields),
                    response_fields=frozenset(response_fields),
                )
            )

    return endpoints


def _extract_schema_fields(request_body: object) -> set[str]:
    """Extract field names from an OpenAPI requestBody."""
    if not isinstance(request_body, dict):
        return set()
    content = request_body.get("content", {})
    if not isinstance(content, dict):
        return set()
    for _media_type, media_obj in content.items():
        if isinstance(media_obj, dict):
            schema = media_obj.get("schema", {})
            if isinstance(schema, dict):
                return set(schema.get("properties", {}).keys())
    return set()


def _extract_response_fields(responses: object) -> set[str]:
    """Extract field names from the first successful response schema."""
    if not isinstance(responses, dict):
        return set()
    for code in ("200", "201", "202", "204"):
        resp = responses.get(code, {})
        if isinstance(resp, dict):
            fields = _extract_schema_fields(resp)
            if fields:
                return fields
    return set()


# ── Endpoint extraction ──────────────────────────────────────────────

_FASTAPI_ROUTE = re.compile(
    r"""@(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["']([^"']+)["']"""
)
_EXPRESS_ROUTE = re.compile(
    r"""(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["']([^"']+)["']"""
)


def extract_implemented_endpoints(
    files: list[dict[str, str]],
) -> frozenset[str]:
    """Extract ``METHOD /path`` pairs from implementation files."""
    endpoints: set[str] = set()
    for f in files:
        content = f.get("content", "")
        for pattern in (_FASTAPI_ROUTE, _EXPRESS_ROUTE):
            for match in pattern.finditer(content):
                method = match.group(1).upper()
                path = _normalize_path(match.group(2))
                endpoints.add(f"{method} {path}")
    return frozenset(endpoints)


_HTTPX_CALL = re.compile(r"""client\.(get|post|put|patch|delete)\s*\(\s*["']([^"']+)["']""")
_SUPERTEST_CALL = re.compile(
    r"""request\s*\(.*?\)\.(get|post|put|patch|delete)\s*\(\s*["']([^"']+)["']"""
)
_FETCH_CALL = re.compile(r"""fetch\s*\(\s*["']([^"']+)["']""")


def extract_tested_endpoints(
    files: list[dict[str, str]],
) -> frozenset[str]:
    """Extract ``METHOD /path`` pairs from test files."""
    endpoints: set[str] = set()
    for f in files:
        content = f.get("content", "")
        for pattern in (_HTTPX_CALL, _SUPERTEST_CALL):
            for match in pattern.finditer(content):
                method = match.group(1).upper()
                path = _normalize_path(match.group(2))
                endpoints.add(f"{method} {path}")
        for match in _FETCH_CALL.finditer(content):
            path = _normalize_path(match.group(1))
            endpoints.add(f"GET {path}")
    return frozenset(endpoints)


def _extract_pydantic_fields(files: list[dict[str, str]], model_name: str) -> frozenset[str]:
    """Extract field names from a Pydantic ``BaseModel`` class."""
    pattern = re.compile(
        rf"class\s+{re.escape(model_name)}\s*\(.*?BaseModel.*?\):\s*\n((?:\s+\w+.*\n)*)"
    )
    fields: set[str] = set()
    for f in files:
        content = f.get("content", "")
        for match in pattern.finditer(content):
            body = match.group(1)
            for line in body.splitlines():
                stripped = line.strip()
                if ":" in stripped and not stripped.startswith("#"):
                    field_name = stripped.split(":")[0].strip()
                    if field_name.isidentifier():
                        fields.add(field_name)
    return frozenset(fields)


# ── Main entry ───────────────────────────────────────────────────────


def check_contracts(
    openapi_spec: str,
    impl_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
) -> ContractCheckResult:
    """Check OpenAPI spec against implementation and test files."""
    declared = parse_openapi_spec(openapi_spec)

    if not declared:
        return ContractCheckResult(
            passed=True,
            deviations=(),
            endpoints_declared=0,
            endpoints_implemented=0,
            endpoints_tested=0,
        )

    implemented = extract_implemented_endpoints(impl_files)
    tested = extract_tested_endpoints(test_files)

    declared_keys = {f"{ep.method} {ep.path}" for ep in declared}
    deviations: list[ContractDeviation] = []

    for ep in declared:
        key = f"{ep.method} {ep.path}"
        if key not in implemented:
            deviations.append(
                ContractDeviation(
                    kind="missing_endpoint",
                    endpoint=key,
                    detail=f"Endpoint {key} declared in spec but not found in implementation",
                )
            )
        if key not in tested:
            deviations.append(
                ContractDeviation(
                    kind="missing_test",
                    endpoint=key,
                    detail=f"Endpoint {key} has no test coverage",
                )
            )

    # Pass/fail: only blocking deviations count (missing_test is non-blocking)
    blocking = [d for d in deviations if d.kind != "missing_test"]
    return ContractCheckResult(
        passed=len(blocking) == 0,
        deviations=tuple(deviations),
        endpoints_declared=len(declared_keys),
        endpoints_implemented=len(implemented & declared_keys),
        endpoints_tested=len(tested & declared_keys),
    )
