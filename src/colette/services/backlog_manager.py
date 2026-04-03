"""In-memory backlog manager with immutable patterns (Phase 3)."""

from __future__ import annotations

import uuid

from colette.schemas.backlog import (
    Backlog,
    BacklogPriority,
    ItemStatus,
    Sprint,
    WorkItem,
)

# Priority sort order (lower = higher priority).
_PRIORITY_ORDER = {
    BacklogPriority.P0_CRITICAL: 0,
    BacklogPriority.P1_HIGH: 1,
    BacklogPriority.P2_MEDIUM: 2,
    BacklogPriority.P3_LOW: 3,
}


class BacklogManager:
    """Manages project backlogs and sprints in memory.

    All public methods return new objects — internal state is never
    exposed or mutated through returned references.
    """

    def __init__(self) -> None:
        self._items: dict[str, WorkItem] = {}
        self._sprints: dict[str, Sprint] = {}
        self._project_items: dict[str, list[str]] = {}
        self._project_sprints: dict[str, list[str]] = {}

    def create_work_item(
        self,
        project_id: str,
        item_data: dict[str, object],
    ) -> WorkItem:
        """Create a new work item and add it to the project backlog."""
        item_id = str(item_data.get("id", f"WI-{uuid.uuid4().hex[:8]}"))
        filtered = {k: v for k, v in item_data.items() if k != "id"}
        item = WorkItem.model_validate({"id": item_id, **filtered})

        self._items[item_id] = item
        self._project_items.setdefault(project_id, []).append(item_id)
        return item

    def get_backlog(self, project_id: str) -> Backlog:
        """Return the full backlog for a project."""
        item_ids = self._project_items.get(project_id, [])
        items = [self._items[iid] for iid in item_ids if iid in self._items]

        sprint_ids = self._project_sprints.get(project_id, [])
        sprints = [self._sprints[sid] for sid in sprint_ids if sid in self._sprints]

        return Backlog(project_id=project_id, items=items, sprints=sprints)

    def get_work_item(self, item_id: str) -> WorkItem | None:
        """Return a single work item by ID, or None."""
        return self._items.get(item_id)

    def update_item_status(self, item_id: str, status: ItemStatus) -> WorkItem:
        """Return a new WorkItem with updated status."""
        item = self._items.get(item_id)
        if item is None:
            msg = f"Work item '{item_id}' not found."
            raise KeyError(msg)

        updated = item.model_copy(update={"status": status})
        self._items[item_id] = updated
        return updated

    def prioritize(self, project_id: str) -> list[WorkItem]:
        """Return backlog items sorted by priority (highest first)."""
        item_ids = self._project_items.get(project_id, [])
        items = [self._items[iid] for iid in item_ids if iid in self._items]
        return sorted(items, key=lambda i: _PRIORITY_ORDER.get(i.priority, 99))

    def create_sprint(
        self,
        project_id: str,
        goal: str,
        item_ids: list[str],
    ) -> Sprint:
        """Create a new sprint and assign work items to it."""
        existing = self._project_sprints.get(project_id, [])
        sprint_number = len(existing) + 1
        sprint_id = f"SPRINT-{project_id}-{sprint_number}"

        sprint = Sprint(
            id=sprint_id,
            project_id=project_id,
            number=sprint_number,
            goal=goal,
            work_items=item_ids,
        )

        self._sprints[sprint_id] = sprint
        self._project_sprints.setdefault(project_id, []).append(sprint_id)

        # Mark items as sprint-scoped.
        for iid in item_ids:
            if iid in self._items:
                self._items[iid] = self._items[iid].model_copy(
                    update={"status": ItemStatus.SPRINT, "sprint_id": sprint_id}
                )

        return sprint

    def get_sprint(self, sprint_id: str) -> Sprint | None:
        """Return a sprint by ID, or None."""
        return self._sprints.get(sprint_id)
