"""Startup cleanup for orphaned pipeline runs and projects.

On server restart, any pipeline_runs or projects stuck in ``"running"``
are artefacts of a previous process that crashed or was killed.  This
module marks them as ``"interrupted"`` and populates the in-memory
:class:`ProjectStatusRegistry` so that LLM calls are blocked for those
projects.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from colette.db.models import PipelineRun, Project
from colette.llm.registry import project_status_registry

logger = structlog.get_logger(__name__)


async def cleanup_stale_runs(session: AsyncSession) -> int:
    """Mark orphaned ``'running'`` records as ``'interrupted'``.

    Also populates the :data:`project_status_registry` so that interrupted
    projects are immediately blocked from making LLM API calls.

    Returns the number of pipeline runs that were cleaned up.
    """
    now = datetime.now(UTC)

    # ── 1. Find running pipeline runs before updating ──────────────────
    stmt = select(PipelineRun.id, PipelineRun.project_id).where(
        PipelineRun.status == "running"
    )
    result = await session.execute(stmt)
    stale_runs = result.all()

    if not stale_runs:
        logger.info("cleanup.no_stale_runs")
        return 0

    stale_project_ids = {str(row.project_id) for row in stale_runs}

    # ── 2. Bulk-update pipeline_runs ───────────────────────────────────
    await session.execute(
        update(PipelineRun)
        .where(PipelineRun.status == "running")
        .values(status="interrupted", completed_at=now)
    )

    # ── 3. Bulk-update projects ────────────────────────────────────────
    await session.execute(
        update(Project)
        .where(Project.status == "running")
        .values(status="interrupted")
    )

    await session.commit()

    # ── 4. Populate the in-memory registry ─────────────────────────────
    for project_id in stale_project_ids:
        project_status_registry.mark(project_id, "interrupted")

    logger.warning(
        "cleanup.stale_runs_interrupted",
        count=len(stale_runs),
        project_ids=sorted(stale_project_ids),
    )
    return len(stale_runs)
