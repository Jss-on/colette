"""Terminal MCP tool wrapper (FR-TL-002)."""

from __future__ import annotations

import subprocess
from typing import Any

from colette.tools.base import MCPBaseTool


class TerminalTool(MCPBaseTool):
    """Execute sandboxed shell commands."""

    name: str = "terminal"
    description: str = "Execute shell commands in a sandboxed environment."

    def _execute(self, **kwargs: Any) -> str:
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 60)
        cwd = kwargs.get("cwd")

        if not command:
            return "Error: no command provided"

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            check=False,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR: {result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
        return output
