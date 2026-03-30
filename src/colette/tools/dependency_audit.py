"""Dependency audit tool — checks for known CVEs (FR-IMP-007)."""

from __future__ import annotations

import subprocess
from typing import Any

from colette.tools.base import MCPBaseTool, validate_path


class DependencyAuditTool(MCPBaseTool):
    """Audit project dependencies for known vulnerabilities."""

    name: str = "dependency_audit"
    description: str = (
        "Audit dependencies for known CVEs using pip-audit (Python) or "
        "npm audit (JS/TS). HIGH/CRITICAL vulnerabilities block inclusion."
    )

    def _execute(self, **kwargs: Any) -> str:
        """Run the appropriate dependency auditor and return output.

        Parameters
        ----------
        path:
            Directory containing the manifest (pyproject.toml or package.json).
        language:
            ``"python"`` (uses pip-audit) or ``"typescript"``/``"javascript"``
            (uses npm audit).
        """
        path = validate_path(kwargs.get("path", "."))
        language: str = kwargs.get("language", "python")
        if language == "python":
            cmd = ["pip-audit", "--desc", "--format=columns"]
        elif language in {"typescript", "javascript"}:
            cmd = ["npm", "audit", "--json"]
        else:
            return f"Unsupported language for dependency audit: {language}"

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=path,
                check=False,
            )
            output = result.stdout or result.stderr or "No vulnerabilities found."
            passed = result.returncode == 0
            return f"AUDIT {'PASSED' if passed else 'FAILED'}\n{output}"
        except FileNotFoundError:
            return f"Audit tool not found: {cmd[0]}. Ensure it is installed."
        except subprocess.TimeoutExpired:
            return "Dependency audit timed out after 120 seconds."
