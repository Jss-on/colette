"""Rich build metadata — computed once at import time.

Exposes version, git commit, build date, Python version, platform,
and environment. Used by CLI ``--version``, ``/health``, and ``/version``
endpoints.
"""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_GIT = "git"


def _run_git(*args: str) -> str:
    """Run a git command and return stripped stdout, or empty string on failure."""
    try:
        return subprocess.check_output(
            [_GIT, *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def _git_info() -> tuple[str, str, str]:
    """Return (short SHA, full SHA, branch) or empty strings on failure."""
    short = _run_git("rev-parse", "--short", "HEAD")
    if not short:
        return "", "", ""
    full = _run_git("rev-parse", "HEAD")
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    return short, full, branch


def _git_dirty() -> bool:
    """Return True if the working tree has uncommitted changes."""
    output = _run_git("status", "--porcelain")
    return bool(output)


@dataclass(frozen=True)
class BuildInfo:
    """Immutable snapshot of build/runtime metadata."""

    version: str
    git_sha_short: str = ""
    git_sha: str = ""
    git_branch: str = ""
    git_dirty: bool = False
    build_date: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    python_version: str = field(default_factory=lambda: platform.python_version())
    platform_system: str = field(default_factory=platform.system)
    platform_machine: str = field(default_factory=platform.machine)
    environment: str = "development"

    @property
    def version_display(self) -> str:
        """Human-readable version string for CLI output.

        Examples:
          0.2.0 (abc1234, main, 2026-04-03T12:00:00Z)
          0.2.0+dirty (abc1234, feat/x, 2026-04-03T12:00:00Z)
        """
        parts = [self.version]
        if self.git_dirty:
            parts[0] += "+dirty"
        meta: list[str] = []
        if self.git_sha_short:
            meta.append(self.git_sha_short)
        if self.git_branch:
            meta.append(self.git_branch)
        meta.append(self.build_date)
        return f"{parts[0]} ({', '.join(meta)})"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON responses."""
        return {
            "version": self.version,
            "git": {
                "sha": self.git_sha,
                "sha_short": self.git_sha_short,
                "branch": self.git_branch,
                "dirty": self.git_dirty,
            },
            "build_date": self.build_date,
            "python": self.python_version,
            "platform": f"{self.platform_system}/{self.platform_machine}",
            "environment": self.environment,
        }


def _resolve_environment() -> str:
    """Detect environment from COLETTE_ENVIRONMENT, falling back to heuristics."""
    env = os.environ.get("COLETTE_ENVIRONMENT", "").lower().strip()
    if env in ("production", "staging", "development", "testing"):
        return env
    # Heuristic: common CI/prod indicators
    if os.environ.get("CI"):
        return "testing"
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return "production"
    return "development"


def get_build_info() -> BuildInfo:
    """Compute build info from runtime context. Cached after first call."""
    from colette import __version__

    short, full, branch = _git_info()
    dirty = _git_dirty() if short else False

    return BuildInfo(
        version=__version__,
        git_sha_short=short,
        git_sha=full,
        git_branch=branch,
        git_dirty=dirty,
        python_version=platform.python_version(),
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        environment=_resolve_environment(),
    )


# Module-level singleton — computed once on first import.
_cached_info: BuildInfo | None = None


def build_info() -> BuildInfo:
    """Return cached BuildInfo singleton."""
    global _cached_info
    if _cached_info is None:
        _cached_info = get_build_info()
    return _cached_info
