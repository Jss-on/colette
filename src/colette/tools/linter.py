"""Linter tool — runs ruff (Python) or ESLint (JS/TS) on generated code (FR-IMP-006)."""

from __future__ import annotations

import subprocess
from typing import Any

from colette.tools.base import MCPBaseTool, validate_path


class LinterTool(MCPBaseTool):
    """Run a linter on a target path and return findings."""

    name: str = "linter"
    description: str = (
        "Run a code linter (ruff for Python, eslint for JS/TS) on the given path. "
        "Returns lint findings as text. Zero errors required before PR creation."
    )

    def _execute(self, **kwargs: Any) -> str:
        """Run the appropriate linter and return output.

        Parameters
        ----------
        path:
            File or directory to lint.
        language:
            ``"python"`` (uses ruff) or ``"typescript"``/``"javascript"`` (uses eslint).
        """
        path = validate_path(kwargs.get("path", "."))
        language: str = kwargs.get("language", "python")
        if language == "python":
            cmd = ["ruff", "check", path, "--output-format=text"]
        elif language in {"typescript", "javascript"}:
            cmd = ["npx", "eslint", path, "--format=stylish"]
        else:
            return f"Unsupported language for linting: {language}"

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            output = result.stdout or result.stderr or "No lint issues found."
            passed = result.returncode == 0
            return f"LINT {'PASSED' if passed else 'FAILED'}\n{output}"
        except FileNotFoundError:
            return f"Linter not found: {cmd[0]}. Ensure it is installed."
        except subprocess.TimeoutExpired:
            return "Linter timed out after 120 seconds."
