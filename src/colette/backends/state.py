"""In-memory state backend for WIP artifacts (Phase 7d)."""

from __future__ import annotations

import fnmatch
import re


class StateBackend:
    """In-memory backend for work-in-progress artifacts."""

    def __init__(self) -> None:
        self._files: dict[str, str] = {}

    async def ls(self, path: str) -> list[str]:
        prefix = path.rstrip("/") + "/"
        return sorted(
            {
                k[len(prefix) :].split("/")[0]
                for k in self._files
                if k.startswith(prefix) or k == path.rstrip("/")
            }
        )

    async def read_file(self, path: str) -> str:
        if path not in self._files:
            msg = f"File not found: {path}"
            raise FileNotFoundError(msg)
        return self._files[path]

    async def write_file(self, path: str, content: str) -> None:
        self._files[path] = content

    async def edit_file(self, path: str, edits: list[dict[str, str]]) -> None:
        content = self._files.get(path, "")
        for edit in edits:
            old = edit.get("old", "")
            new = edit.get("new", "")
            content = content.replace(old, new, 1)
        self._files[path] = content

    async def glob(self, pattern: str) -> list[str]:
        return sorted(k for k in self._files if fnmatch.fnmatch(k, pattern))

    async def grep(self, pattern: str, path: str) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        compiled = re.compile(pattern)
        for fpath, content in self._files.items():
            if fpath.startswith(path):
                for i, line in enumerate(content.splitlines(), 1):
                    if compiled.search(line):
                        results.append(
                            {
                                "file": fpath,
                                "line": str(i),
                                "content": line,
                            }
                        )
        return results
