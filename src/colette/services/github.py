"""GitHub integration — repo creation and file push for generated projects."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx
import structlog

from colette.config import Settings

logger = structlog.get_logger(__name__)


class GitHubError(Exception):
    """Raised when a GitHub API or git operation fails."""


class GitHubService:
    """Creates GitHub repositories and pushes generated project files.

    When ``github_token`` is empty the service reports ``is_configured = False``
    and all public methods become safe no-ops.
    """

    def __init__(self, settings: Settings) -> None:
        self._token = settings.github_token
        self._owner = settings.github_owner
        self._prefix = settings.github_repo_prefix
        self._visibility = settings.github_repo_visibility
        self._api_url = settings.github_api_url.rstrip("/")

    # ── Helpers ────────��─────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        """Return ``True`` when a GitHub token is available."""
        return bool(self._token)

    def generate_repo_name(self, project_name: str, project_id: str) -> str:
        """Build a unique, GitHub-safe repository name.

        Format: ``{prefix}-{sanitized_name}-{8_char_uuid}``
        """
        slug = project_name.lower()
        slug = re.sub(r"[^a-z0-9-]", "-", slug)
        slug = re.sub(r"-{2,}", "-", slug)
        slug = slug.strip("-")
        slug = slug[:40]
        short_id = project_id.replace("-", "")[:8]
        return f"{self._prefix}-{slug}-{short_id}" if slug else f"{self._prefix}-{short_id}"

    # ── GitHub API ──��───────────────────────────────────────────────

    async def create_repository(self, repo_name: str, description: str) -> str:
        """Create a GitHub repository via REST API.

        Returns the HTML URL of the new repository.
        """
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        body: dict[str, Any] = {
            "name": repo_name,
            "description": description[:350] if description else "",
            "private": self._visibility == "private",
            "auto_init": False,
        }

        if self._owner:
            url = f"{self._api_url}/orgs/{self._owner}/repos"
        else:
            url = f"{self._api_url}/user/repos"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body, headers=headers)

        if resp.status_code not in (200, 201):
            detail = resp.text[:500]
            msg = f"GitHub repo creation failed ({resp.status_code}): {detail}"
            raise GitHubError(msg)

        data = resp.json()
        html_url: str = data.get("html_url", "")
        logger.info("github.repo_created", repo_name=repo_name, url=html_url)
        return html_url

    # ── Git operations ─────────��─────────────────────────��──────────

    async def push_files(
        self,
        repo_name: str,
        files: list[dict[str, str]],
        commit_message: str = "Initial commit from Colette",
    ) -> str:
        """Write files to a temp directory and push to GitHub.

        Returns the commit SHA of the initial commit.
        """
        owner = self._owner or await self._get_authenticated_user()
        remote_url = f"https://x-access-token:{self._token}@github.com/{owner}/{repo_name}.git"

        return await asyncio.to_thread(self._push_files_sync, remote_url, files, commit_message)

    def _push_files_sync(
        self,
        remote_url: str,
        files: list[dict[str, str]],
        commit_message: str,
    ) -> str:
        """Synchronous git init → add → commit → push in a temp directory."""
        tmpdir = tempfile.mkdtemp(prefix="colette-git-")
        try:
            # Write all generated files.
            for f in files:
                fpath = Path(tmpdir) / f["path"]
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(f.get("content", ""), encoding="utf-8")

            def _git(*args: str) -> subprocess.CompletedProcess[str]:
                result = subprocess.run(
                    ["git", *args],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                )
                if result.returncode != 0:
                    logger.warning(
                        "git_cmd_failed",
                        args=args,
                        stderr=result.stderr.strip(),
                    )
                    msg = f"git {args[0]} failed: {result.stderr.strip()}"
                    raise GitHubError(msg)
                return result

            _git("init", "-b", "main")
            _git("config", "user.email", "colette@generated.dev")
            _git("config", "user.name", "Colette")
            _git("add", "-A")
            _git("commit", "-m", commit_message)
            _git("remote", "add", "origin", remote_url)
            _git("push", "-u", "origin", "main")

            # Extract commit SHA.
            result = _git("rev-parse", "HEAD")
            return result.stdout.strip()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _get_authenticated_user(self) -> str:
        """Fetch the authenticated user's login from the GitHub API."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self._api_url}/user", headers=headers)
        if resp.status_code != 200:
            msg = f"Failed to fetch GitHub user ({resp.status_code})"
            raise GitHubError(msg)
        login: str = resp.json().get("login", "")
        return login

    # ── Full flow ──────────────���────────────────────────────────────

    async def create_and_push(
        self,
        project_name: str,
        project_id: str,
        description: str,
        files: list[dict[str, str]],
    ) -> tuple[str, str]:
        """Create a repo and push all generated files.

        Returns ``(repo_html_url, repo_name)``.
        """
        repo_name = self.generate_repo_name(project_name, project_id)
        repo_url = await self.create_repository(repo_name, description)
        sha = await self.push_files(repo_name, files)
        logger.info("github.push_complete", repo_name=repo_name, sha=sha)
        return repo_url, repo_name
