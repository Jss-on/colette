"""Composite backend with path-prefix routing (Phase 7d)."""

from __future__ import annotations

from colette.backends.protocol import BackendProtocol


class CompositeBackend:
    """Routes operations to different backends based on path prefix."""

    def __init__(self, routes: dict[str, BackendProtocol], default: BackendProtocol) -> None:
        self._routes = dict(sorted(routes.items(), key=lambda x: -len(x[0])))
        self._default = default

    def _resolve(self, path: str) -> BackendProtocol:
        for prefix, backend in self._routes.items():
            if path.startswith(prefix):
                return backend
        return self._default

    async def ls(self, path: str) -> list[str]:
        return await self._resolve(path).ls(path)

    async def read_file(self, path: str) -> str:
        return await self._resolve(path).read_file(path)

    async def write_file(self, path: str, content: str) -> None:
        await self._resolve(path).write_file(path, content)

    async def edit_file(self, path: str, edits: list[dict[str, str]]) -> None:
        await self._resolve(path).edit_file(path, edits)

    async def glob(self, pattern: str) -> list[str]:
        all_results: list[str] = []
        seen_backends: set[int] = set()
        for backend in [*self._routes.values(), self._default]:
            bid = id(backend)
            if bid not in seen_backends:
                seen_backends.add(bid)
                all_results.extend(await backend.glob(pattern))
        return sorted(set(all_results))

    async def grep(self, pattern: str, path: str) -> list[dict[str, str]]:
        return await self._resolve(path).grep(pattern, path)
