"""Approval workflow routes (NFR-USA-001 — inline approval)."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from colette.api.deps import CurrentUser, get_db, get_pipeline_runner, require_role
from colette.api.schemas import ApprovalResponse, ApproveRequest, RejectRequest
from colette.db.models import ApprovalRecord as ApprovalRecordModel
from colette.db.repositories import ApprovalRecordRepository, PipelineRunRepository
from colette.orchestrator.runner import PipelineRunner
from colette.security.rbac import Permission

logger = structlog.get_logger(__name__)

router = APIRouter()


def _record_to_response(r: ApprovalRecordModel) -> ApprovalResponse:
    return ApprovalResponse(
        id=r.id,
        pipeline_run_id=r.pipeline_run_id,
        request_id=r.request_id,
        stage=r.stage,
        tier=r.tier,
        status=r.status,
        context_summary=r.context_summary,
        proposed_action=r.proposed_action,
        risk_assessment=r.risk_assessment,
        reviewer_id=r.reviewer_id,
        comments=r.comments,
        created_at=r.created_at,
        decided_at=r.decided_at,
    )


@router.get("", response_model=list[ApprovalResponse])
async def list_pending_approvals(
    user: Annotated[CurrentUser, Depends(require_role(Permission.VIEW_PROJECT))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ApprovalResponse]:
    """List all pending approval requests."""
    repo = ApprovalRecordRepository(db)
    records = await repo.list_pending()
    return [_record_to_response(r) for r in records]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Permission.VIEW_PROJECT))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ApprovalResponse:
    """Get a single approval request."""
    repo = ApprovalRecordRepository(db)
    record = await repo.get_by_id(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return _record_to_response(record)


async def _resume_pipeline_bg(
    runner: PipelineRunner,
    project_id: str,
    thread_id: str,
) -> None:
    """Background task: rehydrate, resume, and update DB state."""
    import traceback as tb_mod

    from colette.api.routes.projects import _sanitize_for_json
    from colette.db.session import _session_factory
    from colette.llm.registry import project_status_registry

    try:
        if not runner.is_active(project_id):
            runner.rehydrate(project_id, thread_id)
        state = await runner.resume(project_id)
    except Exception as exc:
        logger.error(
            "approval.resume_failed",
            project_id=project_id,
            error=str(exc),
            traceback=tb_mod.format_exc(),
        )
        project_status_registry.mark(project_id, "failed")
        if _session_factory is not None:
            try:
                async with _session_factory() as session:
                    repo = PipelineRunRepository(session)
                    from colette.db.repositories import ProjectRepository

                    await ProjectRepository(session).update_status(
                        uuid.UUID(project_id), "failed"
                    )
                    runs = await repo.list_for_project(
                        uuid.UUID(project_id), limit=1
                    )
                    if runs:
                        await repo.update_state(runs[0].id, status="failed")
                    await session.commit()
            except Exception as db_exc:
                logger.critical(
                    "approval.db_update_failed",
                    project_id=project_id,
                    error=str(db_exc),
                )
        return

    # Update DB with final state.
    current_status = project_status_registry.get(project_id)
    if _session_factory is not None:
        safe_state = _sanitize_for_json(state)
        try:
            async with _session_factory() as session:
                from colette.db.repositories import ProjectRepository

                await ProjectRepository(session).update_status(
                    uuid.UUID(project_id), current_status or "completed"
                )
                repo = PipelineRunRepository(session)
                runs = await repo.list_for_project(
                    uuid.UUID(project_id), limit=1
                )
                if runs:
                    await repo.update_state(
                        runs[0].id,
                        status=current_status or "completed",
                        state_snapshot=safe_state,
                    )
                    # If awaiting another approval, persist the new records.
                    if current_status == "awaiting_approval":
                        approval_reqs = state.get("approval_requests", [])
                        if approval_reqs:
                            a_repo = ApprovalRecordRepository(session)
                            for req in approval_reqs:
                                await a_repo.create(
                                    pipeline_run_id=runs[0].id,
                                    request_id=req.get("request_id", ""),
                                    stage=req.get("stage", ""),
                                    tier=str(req.get("tier", "")),
                                    context_summary=req.get(
                                        "context_summary", ""
                                    ),
                                    proposed_action=req.get(
                                        "proposed_action", ""
                                    ),
                                    risk_assessment=req.get(
                                        "risk_assessment", ""
                                    ),
                                )
                await session.commit()
        except Exception as db_exc:
            logger.critical(
                "approval.db_update_failed",
                project_id=project_id,
                error=str(db_exc),
            )


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve(
    approval_id: str,
    body: ApproveRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_role(Permission.APPROVE_DECISION))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
    runner: PipelineRunner = Depends(get_pipeline_runner),  # noqa: B008
) -> ApprovalResponse:
    """Approve a pending request and resume the pipeline."""
    repo = ApprovalRecordRepository(db)
    # CLI sends the request_id from the gate event, not the DB primary key.
    record = await repo.get_by_request_id(str(approval_id))
    if record is None:
        try:
            record = await repo.get_by_id(uuid.UUID(str(approval_id)))
        except ValueError:
            pass
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already {record.status}")

    await repo.decide(
        record.id,
        status="approved",
        reviewer_id=body.reviewer_id,
        modifications=body.modifications if body.modifications else None,
        comments=body.comments,
    )

    # Look up the project_id and thread_id from the pipeline run to resume.
    run_repo = PipelineRunRepository(db)
    run = await run_repo.get_by_id(record.pipeline_run_id)
    if run and run.thread_id:
        background_tasks.add_task(
            _resume_pipeline_bg,
            runner,
            str(run.project_id),
            run.thread_id,
        )

    await db.commit()

    updated = await repo.get_by_id(record.id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Approval not found after update")
    return _record_to_response(updated)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject(
    approval_id: str,
    body: RejectRequest,
    user: Annotated[CurrentUser, Depends(require_role(Permission.REJECT_DECISION))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ApprovalResponse:
    """Reject a pending request (accepts DB id or request_id)."""
    repo = ApprovalRecordRepository(db)
    record = await repo.get_by_request_id(str(approval_id))
    if record is None:
        try:
            record = await repo.get_by_id(uuid.UUID(str(approval_id)))
        except ValueError:
            pass
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already {record.status}")

    await repo.decide(
        record.id,
        status="rejected",
        reviewer_id=body.reviewer_id,
        comments=body.reason,
    )
    updated = await repo.get_by_id(record.id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Approval not found after update")
    return _record_to_response(updated)
