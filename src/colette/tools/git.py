"""Git MCP tool wrapper (FR-TL-002).

Provides git status, log, diff, and clone operations via sandboxed subprocesses.
All invocations are audit-logged by the :class:`MCPBaseTool` base class.
"""

from __future__ import annotations

import subprocess
from typing import Any

import structlog

from colette.tools.base import MCPBaseTool

logger = structlog.get_logger(__name__)


class GitTool(MCPBaseTool):
    """Git operations: status, log, diff, clone.

    Supported actions: ``status``, ``log``, ``diff``, ``clone``.
    """

    name: str = "git"
    description: str = "Execute Git commands: status, clone, branch, commit, push."

    def _execute(self, **kwargs: Any) -> str:
        """Dispatch to the requested git action.

        Args:
            **kwargs: Must include ``action`` (status/log/diff/clone)
                and ``repo_path``.  ``clone`` also requires ``url``.

        Returns:
            Command stdout on success, or an error message string.
        """
        action = kwargs.get("action", "status")
        repo_path = kwargs.get("repo_path", ".")

        logger.debug("git_execute", action=action, repo_path=repo_path)

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
            logger.info("git_clone", url=url, repo_path=repo_path)
            cmd = ["git", "clone", url, repo_path]
        else:
            logger.warning("git_unknown_action", action=action)
            return f"Unknown git action: {action}"

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0 and result.stderr:
            logger.warning("git_error", action=action, stderr=result.stderr.strip())
            return f"Error: {result.stderr.strip()}"
        return result.stdout
