"""OpenAPI 3.1 specification validation tool (FR-DES-008).

Validates structure and basic semantics of an OpenAPI JSON spec
without requiring external dependencies.
"""

from __future__ import annotations

import json
from typing import Any

from colette.tools.base import MCPBaseTool

_VALID_HTTP_METHODS = frozenset(
    {"get", "post", "put", "delete", "patch", "options", "head", "trace"}
)
_PATH_LEVEL_KEYS = _VALID_HTTP_METHODS | {"parameters", "summary", "description", "servers"}


class OpenAPIValidatorTool(MCPBaseTool):
    """Validate an OpenAPI 3.1 JSON specification."""

    name: str = "openapi_validator"
    description: str = (
        "Validate an OpenAPI 3.1 JSON specification string. "
        "Returns validation results with any errors found."
    )

    def _execute(self, *, spec: str = "", **kwargs: Any) -> str:
        """Validate OpenAPI spec structure."""
        if not spec:
            return "Error: No OpenAPI spec provided."

        errors: list[str] = []
        try:
            data = json.loads(spec)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON: {exc}"

        if not isinstance(data, dict):
            return "Error: OpenAPI spec must be a JSON object."

        # Required: openapi version
        version = data.get("openapi", "")
        if not version:
            errors.append("Missing required field: 'openapi'")
        elif not str(version).startswith("3."):
            errors.append(f"Expected OpenAPI 3.x, got: {version}")

        # Required: info
        info = data.get("info")
        if info is None:
            errors.append("Missing required field: 'info'")
        elif isinstance(info, dict):
            if "title" not in info:
                errors.append("Missing 'info.title'")
            if "version" not in info:
                errors.append("Missing 'info.version'")
        else:
            errors.append("'info' must be an object")

        # Required: paths
        paths = data.get("paths")
        if paths is None:
            errors.append("Missing required field: 'paths'")
        elif isinstance(paths, dict):
            for path, methods in paths.items():
                if not path.startswith("/"):
                    errors.append(f"Path must start with '/': {path}")
                if isinstance(methods, dict):
                    for key in methods:
                        if key.lower() not in _PATH_LEVEL_KEYS:
                            errors.append(f"Invalid key '{key}' in path '{path}'")
        else:
            errors.append("'paths' must be an object")

        if errors:
            return "Validation FAILED:\n" + "\n".join(f"- {e}" for e in errors)

        path_count = len(data.get("paths", {}))
        return f"Validation PASSED. OpenAPI {version} spec with {path_count} path(s)."
