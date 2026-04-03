"""Backend protocol for artifact storage (Phase 7d)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class BackendProtocol(Protocol):
    """Protocol for artifact storage backends."""

    async def ls(self, path: str) -> list[str]: ...
    async def read_file(self, path: str) -> str: ...
    async def write_file(self, path: str, content: str) -> None: ...
    async def edit_file(self, path: str, edits: list[dict[str, str]]) -> None: ...
    async def glob(self, pattern: str) -> list[str]: ...
    async def grep(self, pattern: str, path: str) -> list[dict[str, str]]: ...


@dataclass
class ExecuteResponse:
    """Response from sandbox command execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SandboxBackendProtocol(BackendProtocol, Protocol):
    """Backend protocol with sandboxed command execution (Phase 7e)."""

    async def execute(
        self,
        command: str,
        timeout: int = 300,
        env: dict[str, str] | None = None,
    ) -> ExecuteResponse: ...
