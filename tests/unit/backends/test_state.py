"""Tests for in-memory state backend (Phase 7d)."""

from __future__ import annotations

import pytest

from colette.backends.state import StateBackend


class TestStateBackend:
    @pytest.mark.asyncio
    async def test_write_and_read(self) -> None:
        be = StateBackend()
        await be.write_file("a.py", "content")
        assert await be.read_file("a.py") == "content"

    @pytest.mark.asyncio
    async def test_read_missing(self) -> None:
        be = StateBackend()
        with pytest.raises(FileNotFoundError):
            await be.read_file("missing.py")

    @pytest.mark.asyncio
    async def test_glob(self) -> None:
        be = StateBackend()
        await be.write_file("src/a.py", "a")
        await be.write_file("src/b.py", "b")
        await be.write_file("tests/c.py", "c")
        result = await be.glob("src/*.py")
        assert result == ["src/a.py", "src/b.py"]

    @pytest.mark.asyncio
    async def test_grep(self) -> None:
        be = StateBackend()
        await be.write_file("src/a.py", "def hello():\n    pass")
        result = await be.grep("hello", "src/")
        assert len(result) == 1
        assert result[0]["file"] == "src/a.py"

    @pytest.mark.asyncio
    async def test_edit_file(self) -> None:
        be = StateBackend()
        await be.write_file("a.py", "old content")
        await be.edit_file("a.py", [{"old": "old", "new": "new"}])
        assert await be.read_file("a.py") == "new content"

    @pytest.mark.asyncio
    async def test_ls(self) -> None:
        be = StateBackend()
        await be.write_file("src/a.py", "a")
        await be.write_file("src/sub/b.py", "b")
        result = await be.ls("src/")
        assert "a.py" in result
