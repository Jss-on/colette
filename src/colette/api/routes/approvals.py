"""Approval workflow routes (NFR-USA-001 — inline approval)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from colette.api.deps import CurrentUser, get_db, require_role
from colette.api.schemas import ApprovalResponse, ApproveRequest, RejectRequest
from colette.db.models import ApprovalRecord as ApprovalRecordModel
from colette.db.repositories import ApprovalRecordRepository
from colette.security.rbac import Permission

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


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve(
    approval_id: uuid.UUID,
    body: ApproveRequest,
    user: Annotated[CurrentUser, Depends(require_role(Permission.APPROVE_DECISION))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ApprovalResponse:
    """Approve a pending request."""
    repo = ApprovalRecordRepository(db)
    record = await repo.get_by_id(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already {record.status}")

    await repo.decide(
        approval_id,
        status="approved",
        reviewer_id=body.reviewer_id,
        modifications=body.modifications if body.modifications else None,
        comments=body.comments,
    )
    updated = await repo.get_by_id(approval_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Approval not found after update")
    return _record_to_response(updated)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject(
    approval_id: uuid.UUID,
    body: RejectRequest,
    user: Annotated[CurrentUser, Depends(require_role(Permission.REJECT_DECISION))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ApprovalResponse:
    """Reject a pending request."""
    repo = ApprovalRecordRepository(db)
    record = await repo.get_by_id(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already {record.status}")

    await repo.decide(
        approval_id,
        status="rejected",
        reviewer_id=body.reviewer_id,
        comments=body.reason,
    )
    updated = await repo.get_by_id(approval_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Approval not found after update")
    return _record_to_response(updated)
