"""Tests for the OpenAPI validator tool."""

from __future__ import annotations

import json

import pytest

from colette.tools.openapi_validator import OpenAPIValidatorTool


@pytest.fixture
def validator() -> OpenAPIValidatorTool:
    return OpenAPIValidatorTool()


def _valid_spec() -> str:
    return json.dumps(
        {
            "openapi": "3.1.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/api/v1/items": {
                    "get": {"summary": "List items"},
                    "post": {"summary": "Create item"},
                },
            },
        }
    )


class TestOpenAPIValidator:
    def test_valid_spec_passes(self, validator: OpenAPIValidatorTool) -> None:
        result = validator._run(spec=_valid_spec())
        assert "PASSED" in result
        assert "1 path(s)" in result

    def test_empty_spec(self, validator: OpenAPIValidatorTool) -> None:
        result = validator._run(spec="")
        assert "Error" in result

    def test_invalid_json(self, validator: OpenAPIValidatorTool) -> None:
        result = validator._run(spec="not json")
        assert "Invalid JSON" in result

    def test_missing_openapi_field(self, validator: OpenAPIValidatorTool) -> None:
        spec = json.dumps({"info": {"title": "T", "version": "1"}, "paths": {}})
        result = validator._run(spec=spec)
        assert "FAILED" in result
        assert "openapi" in result.lower()

    def test_wrong_openapi_version(self, validator: OpenAPIValidatorTool) -> None:
        spec = json.dumps(
            {
                "openapi": "2.0",
                "info": {"title": "T", "version": "1"},
                "paths": {},
            }
        )
        result = validator._run(spec=spec)
        assert "FAILED" in result

    def test_missing_info(self, validator: OpenAPIValidatorTool) -> None:
        spec = json.dumps({"openapi": "3.1.0", "paths": {}})
        result = validator._run(spec=spec)
        assert "FAILED" in result
        assert "info" in result.lower()

    def test_missing_paths(self, validator: OpenAPIValidatorTool) -> None:
        spec = json.dumps(
            {
                "openapi": "3.1.0",
                "info": {"title": "T", "version": "1"},
            }
        )
        result = validator._run(spec=spec)
        assert "FAILED" in result
        assert "paths" in result.lower()

    def test_invalid_path_prefix(self, validator: OpenAPIValidatorTool) -> None:
        spec = json.dumps(
            {
                "openapi": "3.1.0",
                "info": {"title": "T", "version": "1"},
                "paths": {"no-slash": {"get": {}}},
            }
        )
        result = validator._run(spec=spec)
        assert "FAILED" in result
        assert "no-slash" in result

    def test_oversized_spec_rejected(self, validator: OpenAPIValidatorTool) -> None:
        huge_spec = "{" + " " * 1_100_000 + "}"
        result = validator._run(spec=huge_spec)
        assert "exceeds maximum size" in result

    def test_empty_paths_is_valid(self, validator: OpenAPIValidatorTool) -> None:
        spec = json.dumps(
            {
                "openapi": "3.1.0",
                "info": {"title": "T", "version": "1"},
                "paths": {},
            }
        )
        result = validator._run(spec=spec)
        assert "PASSED" in result
        assert "0 path(s)" in result
