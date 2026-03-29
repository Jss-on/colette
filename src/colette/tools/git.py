"""Git MCP tool wrapper (FR-TL-002)."""

from __future__ import annotations

import subprocess
from typing import Any

from colette.tools.base import MCPBaseTool


class GitTool(MCPBaseTool):
    """Git operations: status, clone, branch, commit, push."""

    name: str = "git"
    description: str = "Execute Git commands: status, clone, branch, commit, push."

    def _execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "status")
        repo_path = kwargs.get("repo_path", ".")

        cmd: list[str]
        if action == "status":
            cmd = ["git", "-C", repo_path, "status"]
        elif action == "log":
            count = kwargs.get("count", 10)
            cmd = ["git", "-C", repo_path, "log", "--oneline", f"-{count}"]
        elif action == "diff":
            cmd = ["git", "-C", repo_path, "diff"]
        elif action == "clone":
            url = kwargs.get("url", "")
            cmd = ["git", "clone", url, repo_path]
        else:
            return f"Unknown git action: {action}"

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0 and result.stderr:
            return f"Error: {result.stderr.strip()}"
        return result.stdout
