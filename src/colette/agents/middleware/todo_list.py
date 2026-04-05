"""Todo list middleware — tracks agent task decomposition (Phase 7a)."""

from __future__ import annotations

from dataclasses import dataclass

from colette.agents.middleware.protocol import AgentRequest, AgentResponse, Handler


@dataclass
class TodoItem:
    """A single todo tracked by the middleware."""

    id: str
    description: str
    completed: bool = False


class TodoListMiddleware:
    """Provides todo tracking for agent task decomposition.

    Injects current todo state into the request metadata and
    tracks progress across calls.
    """

    def __init__(self) -> None:
        self._todos: list[TodoItem] = []

    @property
    def todos(self) -> list[TodoItem]:
        """Return a copy of the current todo list."""
        return list(self._todos)

    @property
    def pending_count(self) -> int:
        """Number of incomplete todos."""
        return sum(1 for t in self._todos if not t.completed)

    def add_todo(self, todo_id: str, description: str) -> TodoItem:
        """Add a new todo item."""
        item = TodoItem(id=todo_id, description=description)
        self._todos.append(item)
        return item

    def complete_todo(self, todo_id: str) -> bool:
        """Mark a todo as completed. Returns True if found."""
        for todo in self._todos:
            if todo.id == todo_id:
                todo.completed = True
                return True
        return False

    async def __call__(
        self,
        request: AgentRequest,
        next_handler: Handler,
    ) -> AgentResponse:
        # Inject todo state into request metadata.
        request.metadata["todos"] = [
            {"id": t.id, "description": t.description, "completed": t.completed}
            for t in self._todos
        ]
        request.metadata["pending_todos"] = self.pending_count

        return await next_handler(request)
