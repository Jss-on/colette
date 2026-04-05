"""Tests for todo list middleware (Phase 7a)."""

from __future__ import annotations

import pytest

from colette.agents.middleware.protocol import AgentRequest, AgentResponse
from colette.agents.middleware.todo_list import TodoListMiddleware


async def _capture_handler(request: AgentRequest) -> AgentResponse:
    return AgentResponse(metadata={"captured_todos": request.metadata.get("todos")})


class TestTodoListMiddleware:
    def test_add_todo(self) -> None:
        mw = TodoListMiddleware()
        item = mw.add_todo("T-1", "Write tests")
        assert item.id == "T-1"
        assert item.completed is False
        assert mw.pending_count == 1

    def test_complete_todo(self) -> None:
        mw = TodoListMiddleware()
        mw.add_todo("T-1", "Write tests")
        assert mw.complete_todo("T-1") is True
        assert mw.pending_count == 0

    def test_complete_nonexistent(self) -> None:
        mw = TodoListMiddleware()
        assert mw.complete_todo("FAKE") is False

    def test_todos_copy(self) -> None:
        mw = TodoListMiddleware()
        mw.add_todo("T-1", "Test")
        todos = mw.todos
        assert len(todos) == 1
        todos.clear()
        assert len(mw.todos) == 1  # original unchanged

    @pytest.mark.asyncio
    async def test_injects_todos_into_metadata(self) -> None:
        mw = TodoListMiddleware()
        mw.add_todo("T-1", "Build")
        req = AgentRequest(system_prompt="", user_content="")
        resp = await mw(req, _capture_handler)
        todos = resp.metadata["captured_todos"]
        assert len(todos) == 1
        assert todos[0]["id"] == "T-1"

    @pytest.mark.asyncio
    async def test_injects_pending_count(self) -> None:
        mw = TodoListMiddleware()
        mw.add_todo("T-1", "A")
        mw.add_todo("T-2", "B")
        mw.complete_todo("T-1")
        req = AgentRequest(system_prompt="", user_content="")
        await mw(req, _capture_handler)
        assert req.metadata["pending_todos"] == 1
