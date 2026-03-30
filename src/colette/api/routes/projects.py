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
    """Background task: run the pipeline and update project status on completion."""
    if session_factory is None:
        return
    try:
        await runner.run(project_id, user_request=user_request)
        async with session_factory() as session:
            repo = ProjectRepository(session)
            await repo.update_status(uuid.UUID(project_id), "completed")
            await session.commit()
    except Exception:
        async with session_factory() as session:
            repo = ProjectRepository(session)
            await repo.update_status(uuid.UUID(project_id), "failed")
            await session.commit()


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

    # Start pipeline in background.
    from colette.db.session import _session_factory

    background_tasks.add_task(
        _run_pipeline_bg, runner, str(project.id), body.user_request, _session_factory
    )

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
