"""Repository layer — encapsulates DB access behind a clean interface."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from colette.db.models import (
    ApprovalRecord,
    Artifact,
    PipelineRun,
    Project,
    StageExecution,
    User,
)

# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectRepository:
    """CRUD operations for projects."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str = "Untitled",
        description: str = "",
        user_request: str = "",
        owner_id: uuid.UUID | None = None,
    ) -> Project:
        project = Project(
            name=name,
            description=description,
            user_request=user_request,
            owner_id=owner_id,
        )
        self._session.add(project)
        await self._session.flush()
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
    ) -> list[Project]:
        stmt = select(Project).order_by(Project.created_at.desc()).offset(offset).limit(limit)
        if status:
            stmt = stmt.where(Project.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, project_id: uuid.UUID, status: str) -> None:
        stmt = update(Project).where(Project.id == project_id).values(status=status)
        await self._session.execute(stmt)


# ---------------------------------------------------------------------------
# PipelineRun
# ---------------------------------------------------------------------------


class PipelineRunRepository:
    """CRUD operations for pipeline runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        thread_id: str,
        state_snapshot: dict[str, Any] | None = None,
    ) -> PipelineRun:
        run = PipelineRun(
            project_id=project_id,
            thread_id=thread_id,
            state_snapshot=state_snapshot or {},
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> PipelineRun | None:
        return await self._session.get(PipelineRun, run_id)

    async def get_by_thread_id(self, thread_id: str) -> PipelineRun | None:
        stmt = select(PipelineRun).where(PipelineRun.thread_id == thread_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_for_project(self, project_id: uuid.UUID) -> PipelineRun | None:
        stmt = (
            select(PipelineRun)
            .where(PipelineRun.project_id == project_id, PipelineRun.status == "running")
            .order_by(PipelineRun.started_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_state(
        self,
        run_id: uuid.UUID,
        *,
        state_snapshot: dict[str, Any] | None = None,
        status: str | None = None,
        current_stage: str | None = None,
        total_tokens: int | None = None,
    ) -> None:
        values: dict[str, Any] = {}
        if state_snapshot is not None:
            values["state_snapshot"] = state_snapshot
        if status is not None:
            values["status"] = status
        if current_stage is not None:
            values["current_stage"] = current_stage
        if total_tokens is not None:
            values["total_tokens"] = total_tokens
        if values:
            stmt = update(PipelineRun).where(PipelineRun.id == run_id).values(**values)
            await self._session.execute(stmt)

    async def list_for_project(
        self, project_id: uuid.UUID, *, limit: int = 10
    ) -> list[PipelineRun]:
        stmt = (
            select(PipelineRun)
            .where(PipelineRun.project_id == project_id)
            .order_by(PipelineRun.started_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# StageExecution
# ---------------------------------------------------------------------------


class StageExecutionRepository:
    """CRUD for stage execution records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        pipeline_run_id: uuid.UUID,
        stage: str,
    ) -> StageExecution:
        execution = StageExecution(pipeline_run_id=pipeline_run_id, stage=stage)
        self._session.add(execution)
        await self._session.flush()
        return execution

    async def update_status(
        self,
        execution_id: uuid.UUID,
        *,
        status: str,
        gate_result: dict[str, Any] | None = None,
        tokens_used: int | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status}
        if gate_result is not None:
            values["gate_result"] = gate_result
        if tokens_used is not None:
            values["tokens_used"] = tokens_used
        stmt = update(StageExecution).where(StageExecution.id == execution_id).values(**values)
        await self._session.execute(stmt)


# ---------------------------------------------------------------------------
# ApprovalRecord
# ---------------------------------------------------------------------------


class ApprovalRecordRepository:
    """CRUD for approval records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        pipeline_run_id: uuid.UUID,
        request_id: str,
        stage: str,
        tier: str,
        context_summary: str = "",
        proposed_action: str = "",
        risk_assessment: str = "",
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            pipeline_run_id=pipeline_run_id,
            request_id=request_id,
            stage=stage,
            tier=tier,
            context_summary=context_summary,
            proposed_action=proposed_action,
            risk_assessment=risk_assessment,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_id(self, record_id: uuid.UUID) -> ApprovalRecord | None:
        return await self._session.get(ApprovalRecord, record_id)

    async def get_by_request_id(self, request_id: str) -> ApprovalRecord | None:
        stmt = select(ApprovalRecord).where(ApprovalRecord.request_id == request_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pending(self, *, limit: int = 50) -> list[ApprovalRecord]:
        stmt = (
            select(ApprovalRecord)
            .where(ApprovalRecord.status == "pending")
            .order_by(ApprovalRecord.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def decide(
        self,
        record_id: uuid.UUID,
        *,
        status: str,
        reviewer_id: str,
        modifications: dict[str, Any] | None = None,
        comments: str = "",
    ) -> None:
        from datetime import UTC, datetime

        values: dict[str, Any] = {
            "status": status,
            "reviewer_id": reviewer_id,
            "comments": comments,
            "decided_at": datetime.now(UTC),
        }
        if modifications is not None:
            values["modifications"] = modifications
        stmt = update(ApprovalRecord).where(ApprovalRecord.id == record_id).values(**values)
        await self._session.execute(stmt)


# ---------------------------------------------------------------------------
# Artifact
# ---------------------------------------------------------------------------


class ArtifactRepository:
    """CRUD for generated artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        pipeline_run_id: uuid.UUID,
        path: str,
        content_type: str = "text/plain",
        size_bytes: int = 0,
        storage_key: str = "",
        language: str = "",
    ) -> Artifact:
        artifact = Artifact(
            pipeline_run_id=pipeline_run_id,
            path=path,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            language=language,
        )
        self._session.add(artifact)
        await self._session.flush()
        return artifact

    async def list_for_run(self, pipeline_run_id: uuid.UUID) -> list[Artifact]:
        stmt = (
            select(Artifact)
            .where(Artifact.pipeline_run_id == pipeline_run_id)
            .order_by(Artifact.path)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserRepository:
    """CRUD for users."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        username: str,
        role: str = "observer",
        api_key_hash: str = "",
    ) -> User:
        user = User(username=username, role=role, api_key_hash=api_key_hash)
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_api_key_hash(self, api_key_hash: str) -> User | None:
        stmt = select(User).where(User.api_key_hash == api_key_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
