"""Filesystem MCP tool wrapper (FR-TL-002)."""

from __future__ import annotations

import subprocess
from typing import Any

from colette.tools.base import MCPBaseTool


class FilesystemTool(MCPBaseTool):
    """Read, write, and search files via subprocess."""

    name: str = "filesystem"
    description: str = "Read, write, search, and list files on the filesystem."

    def _execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "read")
        path = kwargs.get("path", ".")

        if action == "read":
            result = subprocess.run(                ["cat", path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        elif action == "list":
            result = subprocess.run(                ["ls", "-la", path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        elif action == "search":
            pattern = kwargs.get("pattern", "")
            result = subprocess.run(                ["grep", "-r", pattern, path],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        else:
            return f"Unknown action: {action}"

        if result.returncode != 0 and result.stderr:
            return f"Error: {result.stderr.strip()}"
        return result.stdout
