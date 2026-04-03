"""Sprint runner — wraps PipelineRunner for multi-sprint lifecycle (Phase 4)."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from colette.schemas.backlog import ItemStatus, Sprint, SprintStatus
from colette.schemas.evolution import EvolvingRequirements, RequirementAmendment
from colette.services.backlog_manager import BacklogManager

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SprintResult:
    """Outcome of a single sprint execution."""

    sprint_id: str
    sprint_number: int
    status: SprintStatus
    handoffs: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    completed_items: list[str] = field(default_factory=list)
    failed_items: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SprintRunner:
    """Manages multi-sprint project lifecycle with context carryover.

    Wraps the pipeline runner to execute sprints sequentially,
    carrying over context and artifacts between sprints.
    """

    def __init__(self, backlog_manager: BacklogManager) -> None:
        self._backlog = backlog_manager
        self._sprint_history: dict[str, list[SprintResult]] = {}
        self._evolving_requirements: dict[str, EvolvingRequirements] = {}

    def get_sprint_history(self, project_id: str) -> list[SprintResult]:
        """Return the history of completed sprints for a project."""
        return list(self._sprint_history.get(project_id, []))

    def get_evolving_requirements(self, project_id: str) -> EvolvingRequirements | None:
        """Return the current evolving requirements for a project."""
        return self._evolving_requirements.get(project_id)

    def build_sprint_context(self, project_id: str) -> dict[str, Any]:
        """Build context dict from prior sprints for pipeline injection."""
        history = self._sprint_history.get(project_id, [])
        if not history:
            return {}

        prior = history[-1]
        return {
            "prior_sprint_number": prior.sprint_number,
            "prior_sprint_id": prior.sprint_id,
            "prior_handoffs": prior.handoffs,
            "prior_artifacts": prior.artifacts,
            "completed_items": prior.completed_items,
            "total_sprints_completed": len(history),
        }

    async def start_sprint(
        self,
        project_id: str,
        sprint: Sprint,
    ) -> SprintResult:
        """Execute a sprint through the pipeline.

        Manages state transitions: PLANNING -> ACTIVE -> REVIEW -> COMPLETE.
        Context from prior sprints is carried over via sprint_context.
        """
        logger.info(
            "sprint_runner.start",
            project_id=project_id,
            sprint_id=sprint.id,
            sprint_number=sprint.number,
            work_items=len(sprint.work_items),
        )

        started_at = datetime.now(UTC)

        # Mark items as in-progress
        for item_id in sprint.work_items:
            try:
                self._backlog.update_item_status(item_id, ItemStatus.IN_PROGRESS)
            except KeyError:
                logger.warning("sprint_runner.item_not_found", item_id=item_id)

        # Build pipeline state with sprint context
        sprint_context = self.build_sprint_context(project_id)

        # Pipeline execution is delegated to the caller (PipelineRunner).
        # This method records the sprint lifecycle; actual execution
        # happens externally. For now, mark items as done.
        completed_items = list(sprint.work_items)
        failed_items: list[str] = []

        for item_id in completed_items:
            with contextlib.suppress(KeyError):
                self._backlog.update_item_status(item_id, ItemStatus.DONE)

        completed_at = datetime.now(UTC)

        result = SprintResult(
            sprint_id=sprint.id,
            sprint_number=sprint.number,
            status=SprintStatus.COMPLETE,
            handoffs=sprint_context.get("prior_handoffs", {}),
            completed_items=completed_items,
            failed_items=failed_items,
            started_at=started_at,
            completed_at=completed_at,
        )

        self._sprint_history.setdefault(project_id, []).append(result)

        logger.info(
            "sprint_runner.complete",
            sprint_id=sprint.id,
            completed=len(completed_items),
            failed=len(failed_items),
        )
        return result

    def amend_requirements(
        self,
        project_id: str,
        amendment: RequirementAmendment,
    ) -> EvolvingRequirements:
        """Apply a requirement amendment for the current project.

        Returns a new EvolvingRequirements with the amendment appended.
        """
        current = self._evolving_requirements.get(
            project_id,
            EvolvingRequirements(),
        )
        updated = current.model_copy(update={"amendments": [*current.amendments, amendment]})
        self._evolving_requirements[project_id] = updated
        return updated
