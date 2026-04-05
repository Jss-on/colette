"""Tests for composite backend (Phase 7d)."""

from __future__ import annotations

import pytest

from colette.backends.composite import CompositeBackend
from colette.backends.state import StateBackend


class TestCompositeBackend:
    @pytest.mark.asyncio
    async def test_routes_by_prefix(self) -> None:
        src_be = StateBackend()
        test_be = StateBackend()
        default_be = StateBackend()

        comp = CompositeBackend(
            {"src/": src_be, "tests/": test_be},
            default_be,
        )

        await comp.write_file("src/a.py", "source")
        await comp.write_file("tests/t.py", "test")
        await comp.write_file("README.md", "readme")

        assert await src_be.read_file("src/a.py") == "source"
        assert await test_be.read_file("tests/t.py") == "test"
        assert await default_be.read_file("README.md") == "readme"

    @pytest.mark.asyncio
    async def test_read_through_composite(self) -> None:
        be = StateBackend()
        comp = CompositeBackend({}, be)
        await be.write_file("a.py", "content")
        assert await comp.read_file("a.py") == "content"

    @pytest.mark.asyncio
    async def test_glob_across_backends(self) -> None:
        be1 = StateBackend()
        be2 = StateBackend()
        await be1.write_file("src/a.py", "a")
        await be2.write_file("tests/b.py", "b")

        comp = CompositeBackend({"src/": be1, "tests/": be2}, StateBackend())
        result = await comp.glob("**/*.py")
        assert "src/a.py" in result
