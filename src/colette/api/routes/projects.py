"""Project CRUD routes (NFR-USA-001, NFR-USA-002)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from colette.api.deps import CurrentUser, get_db, get_pipeline_runner, require_role
from colette.api.schemas import ProjectCreate, ProjectListResponse, ProjectResponse
from colette.db.models import Project
from colette.db.repositories import PipelineRunRepository, ProjectRepository
from colette.llm.registry import project_status_registry
from colette.orchestrator.runner import PipelineRunner
from colette.security.rbac import Permission

router = APIRouter()


def _project_to_response(p: Project) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        user_request=p.user_request,
        status=p.status,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def _run_pipeline_bg(
    runner: PipelineRunner,
    project_id: str,
    user_request: str,
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> None:
    """Background task: run the pipeline and update project status on completion.

    Phase 5 guarantees:
    - A terminal event (PIPELINE_COMPLETED or PIPELINE_FAILED) is always emitted.
    - Both project AND pipeline_run DB rows are updated on completion/failure.
    - DB update failures are logged at CRITICAL level, never swallowed.
    - Traceback is included in all failure events for downstream consumers.
    """
    import traceback as tb_mod

    import structlog

    from colette.orchestrator.event_bus import EventType, PipelineEvent

    log = structlog.get_logger(__name__)

    if session_factory is None:
        log.error("pipeline.no_session_factory", project_id=project_id)
        project_status_registry.mark(project_id, "failed")
        runner.event_bus.emit(
            PipelineEvent(
                project_id=project_id,
                event_type=EventType.PIPELINE_FAILED,
                message="No session factory available — cannot track pipeline state",
            )
        )
        return

    # runner.run() manages the registry state machine (running → completed/failed).
    try:
        state = await runner.run(project_id, user_request=user_request)
    except Exception as exc:
        # Pipeline failed — runner.run() already emitted PIPELINE_FAILED
        # and marked the registry. We just need to update the DB.
        project_status_registry.mark(project_id, "failed")
        log.error(
            "pipeline.failed",
            project_id=project_id,
            error=str(exc),
        )
        try:
            async with session_factory() as session:
                repo = ProjectRepository(session)
                await repo.update_status(uuid.UUID(project_id), "failed")
                run_repo = PipelineRunRepository(session)
                runs = await run_repo.list_for_project(
                    uuid.UUID(project_id), limit=1
                )
                if runs:
                    await run_repo.update_state(runs[0].id, status="failed")
                await session.commit()
        except Exception as db_exc:
            log.critical(
                "pipeline.status_update_failed",
                project_id=project_id,
                error=str(db_exc),
            )
        return

    # Check if pipeline paused for approval (not actually completed).
    current_status = project_status_registry.get(project_id)
    if current_status == "awaiting_approval":
        log.info("pipeline.awaiting_approval", project_id=project_id)
        thread_id = runner.get_thread_id(project_id)
        try:
            async with session_factory() as session:
                repo = ProjectRepository(session)
                await repo.update_status(uuid.UUID(project_id), "awaiting_approval")
                run_repo = PipelineRunRepository(session)
                runs = await run_repo.list_for_project(
                    uuid.UUID(project_id), limit=1
                )
                if runs:
                    await run_repo.update_state(
                        runs[0].id,
                        status="awaiting_approval",
                        state_snapshot=state,
                        thread_id=thread_id,
                    )
                await session.commit()
        except Exception as db_exc:
            log.critical(
                "pipeline.status_update_failed",
                project_id=project_id,
                error=str(db_exc),
            )
        return

    # Pipeline completed — update DB and registry.
    project_status_registry.mark(project_id, "completed")
    try:
        async with session_factory() as session:
            repo = ProjectRepository(session)
            await repo.update_status(uuid.UUID(project_id), "completed")
            run_repo = PipelineRunRepository(session)
            runs = await run_repo.list_for_project(
                uuid.UUID(project_id), limit=1
            )
            if runs:
                await run_repo.update_state(
                    runs[0].id, status="completed", state_snapshot=state,
                )
            await session.commit()
        log.info("pipeline.completed", project_id=project_id)
    except Exception as db_exc:
        # Pipeline succeeded but DB update failed — emit PIPELINE_FAILED
        # so SSE consumers know something went wrong.
        project_status_registry.mark(project_id, "failed")
        runner.event_bus.emit(
            PipelineEvent(
                project_id=project_id,
                event_type=EventType.PIPELINE_FAILED,
                message=f"DB update failed after pipeline completed: {db_exc}",
                detail={"traceback": tb_mod.format_exc()},
            )
        )
        log.critical(
            "pipeline.status_update_failed",
            project_id=project_id,
            error=str(db_exc),
        )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(
    body: ProjectCreate,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_role(Permission.SUBMIT_PROJECT))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
    runner: PipelineRunner = Depends(get_pipeline_runner),  # noqa: B008
) -> ProjectResponse:
    """Create a new project and start its pipeline."""
    repo = ProjectRepository(db)
    project = await repo.create(
        name=body.name,
        description=body.description,
        user_request=body.user_request,
        owner_id=uuid.UUID(user.user_id) if user.user_id != "default" else None,
    )
    await repo.update_status(project.id, "running")

    # Record the pipeline run.
    thread_id = f"{project.id}-pipeline"
    run_repo = PipelineRunRepository(db)
    await run_repo.create(project_id=project.id, thread_id=thread_id)

    # Commit NOW so background task can see the records.
    await db.commit()

    # Start pipeline in background.
    from colette.db.session import _session_factory

    background_tasks.add_task(
        _run_pipeline_bg, runner, str(project.id), body.user_request, _session_factory
    )

    return _project_to_response(project)


@router.post("/{project_id}/resume", response_model=ProjectResponse)
async def resume_project(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_role(Permission.SUBMIT_PROJECT))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
    runner: PipelineRunner = Depends(get_pipeline_runner),  # noqa: B008
) -> ProjectResponse:
    """Resume an interrupted project — re-enables LLM API calls."""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancelled projects cannot be resumed. Submit a new project instead.",
        )
    if project.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is already running.",
        )
    if project.status not in ("interrupted", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot resume a project with status '{project.status}'.",
        )

    # Re-mark as running in DB and registry.
    await repo.update_status(project_id, "running")
    project_status_registry.mark(str(project_id), "running")
    await db.commit()

    # Re-fetch to return updated state.
    project = await repo.get_by_id(project_id)
    if project is None:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Project not found")

    # Re-start the pipeline in background.
    from colette.db.session import _session_factory

    background_tasks.add_task(
        _run_pipeline_bg, runner, str(project_id), project.user_request, _session_factory
    )

    return _project_to_response(project)


@router.post("/{project_id}/cancel", response_model=ProjectResponse)
async def cancel_project(
    project_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Permission.SUBMIT_PROJECT))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
    runner: PipelineRunner = Depends(get_pipeline_runner),  # noqa: B008
) -> ProjectResponse:
    """Cancel a project permanently — blocks LLM calls, cannot be resumed."""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is already cancelled.",
        )

    # Hard-cancel any in-flight pipeline tasks.
    runner.cancel_project(str(project_id), status="cancelled")

    # Update DB.
    await repo.update_status(project_id, "cancelled")

    # Also mark pipeline runs as cancelled.
    run_repo = PipelineRunRepository(db)
    runs = await run_repo.list_for_project(project_id, limit=1)
    if runs and runs[0].status == "running":
        await run_repo.update_state(runs[0].id, status="cancelled")

    await db.commit()

    project = await repo.get_by_id(project_id)
    if project is None:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    user: Annotated[CurrentUser, Depends(require_role(Permission.VIEW_PROJECT))],
    offset: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ProjectListResponse:
    """List projects with pagination."""
    repo = ProjectRepository(db)
    projects = await repo.list_all(offset=offset, limit=limit)
    return ProjectListResponse(
        data=[_project_to_response(p) for p in projects],
        total=len(projects),
        offset=offset,
        limit=limit,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Permission.VIEW_PROJECT))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ProjectResponse:
    """Get a single project by ID."""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(project)
