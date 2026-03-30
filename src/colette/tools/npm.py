"""npm tool — frontend package management (FR-IMP-007)."""

from __future__ import annotations

import subprocess
from typing import Any

from colette.tools.base import MCPBaseTool, validate_path

_ALLOWED_COMMANDS = frozenset({"install", "ci", "list", "outdated", "init"})


class NpmTool(MCPBaseTool):
    """Run npm commands for frontend package management."""

    name: str = "npm"
    description: str = (
        "Run npm commands (install, ci, list, outdated, init) for "
        "managing frontend JavaScript/TypeScript dependencies."
    )

    def _execute(self, **kwargs: Any) -> str:
        """Run an npm command.

        Parameters
        ----------
        command:
            npm sub-command (install, ci, list, outdated, init).
        args:
            Additional arguments passed to npm.
        cwd:
            Working directory.
        """
        command: str = kwargs.get("command", "")
        args_raw = kwargs.get("args")
        args: list[str] = args_raw if isinstance(args_raw, list) else []
        cwd = validate_path(kwargs.get("cwd", "."))
        if command not in _ALLOWED_COMMANDS:
            return f"Command '{command}' not allowed. Use one of: {sorted(_ALLOWED_COMMANDS)}"

        cmd = ["npm", command, *(args or [])]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=cwd,
                check=False,
            )
            output = result.stdout or result.stderr or f"npm {command} completed."
            return f"EXIT {result.returncode}\n{output}"
        except FileNotFoundError:
            return "npm not found. Ensure Node.js is installed."
        except subprocess.TimeoutExpired:
            return f"npm {command} timed out after 300 seconds."
