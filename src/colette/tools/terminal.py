"""Terminal MCP tool wrapper (FR-TL-002).

Provides sandboxed shell command execution.  All invocations are
audit-logged by the :class:`MCPBaseTool` base class.
"""

from __future__ import annotations

import subprocess
from typing import Any

import structlog

from colette.tools.base import MCPBaseTool

logger = structlog.get_logger(__name__)


class TerminalTool(MCPBaseTool):
    """Execute sandboxed shell commands.

    The command is run via ``subprocess`` with ``shell=True`` and
    configurable timeout / working directory.
    """

    name: str = "terminal"
    description: str = "Execute shell commands in a sandboxed environment."

    def _execute(self, **kwargs: Any) -> str:
        """Run a shell command and return combined stdout/stderr.

        Args:
            **kwargs: Must include ``command``.  Optional: ``timeout``
                (default 60s) and ``cwd`` (working directory).

        Returns:
            Command output including stderr and exit code on failure.
        """
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 60)
        cwd = kwargs.get("cwd")

        if not command:
            return "Error: no command provided"

        logger.debug("terminal_execute", command=command, cwd=cwd, timeout=timeout)

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
            logger.warning(
                "terminal_nonzero_exit",
                command=command,
                exit_code=result.returncode,
            )
            output += f"\nExit code: {result.returncode}"
        return output
