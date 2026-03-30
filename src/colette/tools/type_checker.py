"""Type checker tool — runs mypy (Python) or tsc (TypeScript) (FR-IMP-006)."""

from __future__ import annotations

import subprocess
from typing import Any

from colette.tools.base import MCPBaseTool, validate_path


class TypeCheckerTool(MCPBaseTool):
    """Run a type checker on a target path and return findings."""

    name: str = "type_checker"
    description: str = (
        "Run a type checker (mypy for Python, tsc for TypeScript) on the given path. "
        "Returns type errors as text. Zero type errors required before PR creation."
    )

    def _execute(self, **kwargs: Any) -> str:
        """Run the appropriate type checker and return output.

        Parameters
        ----------
        path:
            File or directory to check.
        language:
            ``"python"`` (uses mypy) or ``"typescript"`` (uses tsc).
        """
        path = validate_path(kwargs.get("path", "."))
        language: str = kwargs.get("language", "python")
        if language == "python":
            cmd = ["mypy", path, "--no-color-output"]
        elif language == "typescript":
            cmd = ["npx", "tsc", "--noEmit", "--pretty", "false"]
        else:
            return f"Unsupported language for type checking: {language}"

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            output = result.stdout or result.stderr or "No type errors found."
            passed = result.returncode == 0
            return f"TYPE CHECK {'PASSED' if passed else 'FAILED'}\n{output}"
        except FileNotFoundError:
            return f"Type checker not found: {cmd[0]}. Ensure it is installed."
        except subprocess.TimeoutExpired:
            return "Type checker timed out after 180 seconds."
