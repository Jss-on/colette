"""Tests for colette.eval.contract_checker."""

from __future__ import annotations

import json

from colette.eval.contract_checker import (
    check_contracts,
    extract_implemented_endpoints,
    extract_tested_endpoints,
    parse_openapi_spec,
)


def _spec(paths: dict) -> str:
    return json.dumps({"openapi": "3.0.0", "paths": paths})


def _file(content: str, path: str = "app.py") -> dict[str, str]:
    return {"path": path, "content": content}


# ── parse_openapi_spec ───────────────────────────────────────────────


class TestParseOpenapiSpec:
    def test_basic_spec(self) -> None:
        spec = _spec(
            {
                "/api/todos": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"properties": {"id": {}, "title": {}}}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        )
        endpoints = parse_openapi_spec(spec)
        assert len(endpoints) == 1
        assert endpoints[0].method == "GET"
        assert endpoints[0].path == "/api/todos"
        assert endpoints[0].response_fields == frozenset({"id", "title"})

    def test_malformed_json(self) -> None:
        assert parse_openapi_spec("{bad json") == []

    def test_empty_spec(self) -> None:
        assert parse_openapi_spec(json.dumps({"paths": {}})) == []


# ── extract_implemented_endpoints ────────────────────────────────────


class TestExtractImplementedEndpoints:
    def test_fastapi_routes(self) -> None:
        code = (
            '@app.get("/api/todos")\n'
            "async def list_todos():\n"
            "    pass\n\n"
            '@app.post("/api/todos")\n'
            "async def create_todo():\n"
            "    pass\n"
        )
        eps = extract_implemented_endpoints([_file(code)])
        assert "GET /api/todos" in eps
        assert "POST /api/todos" in eps

    def test_express_routes(self) -> None:
        code = 'router.get("/api/users", handler);\n'
        eps = extract_implemented_endpoints([_file(code, "routes.js")])
        assert "GET /api/users" in eps


# ── extract_tested_endpoints ─────────────────────────────────────────


class TestExtractTestedEndpoints:
    def test_httpx_calls(self) -> None:
        code = 'response = client.get("/api/todos")\n'
        eps = extract_tested_endpoints([_file(code)])
        assert "GET /api/todos" in eps


# ── check_contracts ──────────────────────────────────────────────────


class TestCheckContracts:
    def test_all_endpoints_match(self) -> None:
        spec = _spec(
            {
                "/api/todos": {"get": {"responses": {}}},
                "/api/todos/{id}": {"get": {"responses": {}}},
                "/api/users": {"post": {"responses": {}}},
            }
        )
        impl = [
            _file(
                '@app.get("/api/todos")\ndef a(): pass\n'
                '@app.get("/api/todos/{id}")\ndef b(): pass\n'
                '@app.post("/api/users")\ndef c(): pass\n'
            )
        ]
        tests = [
            _file(
                'client.get("/api/todos")\nclient.get("/api/todos/1")\nclient.post("/api/users")\n'
            )
        ]
        result = check_contracts(spec, impl, tests)
        assert result.passed is True
        blocking = [d for d in result.deviations if d.kind != "missing_test"]
        assert len(blocking) == 0
        assert result.endpoints_declared == 3

    def test_missing_endpoint(self) -> None:
        spec = _spec(
            {
                "/api/todos": {"get": {"responses": {}}},
                "/api/users": {"get": {"responses": {}}},
                "/api/items": {"post": {"responses": {}}},
            }
        )
        impl = [
            _file('@app.get("/api/todos")\ndef a(): pass\n@app.get("/api/users")\ndef b(): pass\n')
        ]
        result = check_contracts(spec, impl, [])
        missing = [d for d in result.deviations if d.kind == "missing_endpoint"]
        assert len(missing) == 1
        assert result.passed is False

    def test_schema_mismatch_still_passes_if_endpoint_present(self) -> None:
        # Schema mismatch detection is a future enhancement;
        # current implementation checks endpoint presence only
        spec = _spec({"/api/todos": {"get": {"responses": {}}}})
        impl = [_file('@app.get("/api/todos")\ndef a(): pass\n')]
        result = check_contracts(spec, impl, [])
        blocking = [d for d in result.deviations if d.kind == "missing_endpoint"]
        assert len(blocking) == 0

    def test_missing_test_non_blocking(self) -> None:
        spec = _spec({"/api/todos": {"get": {"responses": {}}}})
        impl = [_file('@app.get("/api/todos")\ndef a(): pass\n')]
        result = check_contracts(spec, impl, [])
        missing_tests = [d for d in result.deviations if d.kind == "missing_test"]
        assert len(missing_tests) == 1
        assert result.passed is True

    def test_empty_spec_passes(self) -> None:
        result = check_contracts(json.dumps({"paths": {}}), [], [])
        assert result.passed is True
        assert result.endpoints_declared == 0

    def test_malformed_json_passes(self) -> None:
        result = check_contracts("{bad", [], [])
        assert result.passed is True

    def test_path_normalization(self) -> None:
        spec = _spec({"/api/users/": {"get": {"responses": {}}}})
        impl = [_file('@app.get("/api/users")\ndef a(): pass\n')]
        result = check_contracts(spec, impl, [])
        blocking = [d for d in result.deviations if d.kind == "missing_endpoint"]
        assert len(blocking) == 0
