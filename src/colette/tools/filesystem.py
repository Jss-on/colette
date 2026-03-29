"""Filesystem MCP tool wrapper (FR-TL-002).

Provides file read, list, and search operations via sandboxed subprocesses.
All invocations are audit-logged by the :class:`MCPBaseTool` base class.
"""

from __future__ import annotations

import subprocess
from typing import Any

import structlog

from colette.tools.base import MCPBaseTool

logger = structlog.get_logger(__name__)


class FilesystemTool(MCPBaseTool):
    """Read, write, and search files via subprocess.

    Supported actions: ``read``, ``list``, ``search``.
    """

    name: str = "filesystem"
    description: str = "Read, write, search, and list files on the filesystem."

    def _execute(self, **kwargs: Any) -> str:
        """Dispatch to the requested filesystem action.

        Args:
            **kwargs: Must include ``action`` (read/list/search) and ``path``.
                For ``search``, also requires ``pattern``.

        Returns:
            Command stdout on success, or an error message string.
        """
        action = kwargs.get("action", "read")
        path = kwargs.get("path", ".")

        logger.debug("filesystem_execute", action=action, path=path)

        if action == "read":
            result = subprocess.run(
                ["cat", path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        elif action == "list":
            result = subprocess.run(
                ["ls", "-la", path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        elif action == "search":
            pattern = kwargs.get("pattern", "")
            result = subprocess.run(
                ["grep", "-r", pattern, path],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        else:
            logger.warning("filesystem_unknown_action", action=action)
            return f"Unknown action: {action}"

        if result.returncode != 0 and result.stderr:
            logger.warning(
                "filesystem_error",
                action=action,
                path=path,
                stderr=result.stderr.strip(),
            )
            return f"Error: {result.stderr.strip()}"
        return result.stdout
