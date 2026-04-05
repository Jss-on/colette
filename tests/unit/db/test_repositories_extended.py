"""Extended repository tests — covers query methods and edge cases."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from colette.db.repositories import (
    ApprovalRecordRepository,
    ArtifactRepository,
    PipelineRunRepository,
    ProjectRepository,
    StageExecutionRepository,
    UserRepository,
)


def _mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    return session


# ── ProjectRepository ────────────────────────────────────────────────


class TestProjectRepository:
    @pytest.mark.asyncio
    async def test_create(self) -> None:
        session = _mock_session()
        repo = ProjectRepository(session)
        await repo.create(name="Test", description="desc", user_request="build app")
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        session = _mock_session()
        session.get.return_value = MagicMock(id=uuid.uuid4(), name="P")
        repo = ProjectRepository(session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _mock_session()
        session.get.return_value = None
        repo = ProjectRepository(session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_no_filter(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result
        repo = ProjectRepository(session)
        result = await repo.list_all()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_all_with_status_filter(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result
        repo = ProjectRepository(session)
        result = await repo.list_all(status="running")
        assert result == []
        # Verify execute was called (with status filter added)
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_status(self) -> None:
        session = _mock_session()
        repo = ProjectRepository(session)
        await repo.update_status(uuid.uuid4(), "completed")
        session.execute.assert_awaited_once()


# ── PipelineRunRepository ────────────────────────────────────────────


class TestPipelineRunRepository:
    @pytest.mark.asyncio
    async def test_create(self) -> None:
        session = _mock_session()
        repo = PipelineRunRepository(session)
        await repo.create(project_id=uuid.uuid4(), thread_id="t-1")
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        session = _mock_session()
        session.get.return_value = MagicMock()
        repo = PipelineRunRepository(session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_thread_id(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        session.execute.return_value = mock_result
        repo = PipelineRunRepository(session)
        result = await repo.get_by_thread_id("thread-abc")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_active_for_project(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result
        repo = PipelineRunRepository(session)
        result = await repo.get_active_for_project(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_update_state_all_fields(self) -> None:
        session = _mock_session()
        repo = PipelineRunRepository(session)
        await repo.update_state(
            uuid.uuid4(),
            state_snapshot={"foo": "bar"},
            status="completed",
            current_stage="testing",
            total_tokens=5000,
            thread_id="t-2",
        )
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_state_no_fields(self) -> None:
        session = _mock_session()
        repo = PipelineRunRepository(session)
        await repo.update_state(uuid.uuid4())
        # No execute if no values
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_state_partial(self) -> None:
        session = _mock_session()
        repo = PipelineRunRepository(session)
        await repo.update_state(uuid.uuid4(), status="failed")
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_for_project(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result
        repo = PipelineRunRepository(session)
        result = await repo.list_for_project(uuid.uuid4())
        assert result == []


# ── StageExecutionRepository ─────────────────────────────────────────


class TestStageExecutionRepository:
    @pytest.mark.asyncio
    async def test_create(self) -> None:
        session = _mock_session()
        repo = StageExecutionRepository(session)
        await repo.create(pipeline_run_id=uuid.uuid4(), stage="design")
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_with_gate_result(self) -> None:
        session = _mock_session()
        repo = StageExecutionRepository(session)
        await repo.update_status(
            uuid.uuid4(),
            status="completed",
            gate_result={"passed": True},
            tokens_used=1000,
        )
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_status_minimal(self) -> None:
        session = _mock_session()
        repo = StageExecutionRepository(session)
        await repo.update_status(uuid.uuid4(), status="failed")
        session.execute.assert_awaited_once()


# ── ApprovalRecordRepository ─────────────────────────────────────────


class TestApprovalRecordRepository:
    @pytest.mark.asyncio
    async def test_create(self) -> None:
        session = _mock_session()
        repo = ApprovalRecordRepository(session)
        await repo.create(
            pipeline_run_id=uuid.uuid4(),
            request_id="req-1",
            stage="design",
            tier="T1",
            context_summary="Gate passed",
            proposed_action="Continue",
        )
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        session = _mock_session()
        session.get.return_value = MagicMock()
        repo = ApprovalRecordRepository(session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_request_id(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        session.execute.return_value = mock_result
        repo = ApprovalRecordRepository(session)
        result = await repo.get_by_request_id("req-abc")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_pending(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result
        repo = ApprovalRecordRepository(session)
        result = await repo.list_pending()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_pending_by_run(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result
        repo = ApprovalRecordRepository(session)
        result = await repo.list_pending_by_run(uuid.uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_decide(self) -> None:
        session = _mock_session()
        repo = ApprovalRecordRepository(session)
        await repo.decide(
            uuid.uuid4(),
            status="approved",
            reviewer_id="user-1",
            modifications={"note": "ok"},
            comments="Looks good",
        )
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_decide_without_modifications(self) -> None:
        session = _mock_session()
        repo = ApprovalRecordRepository(session)
        await repo.decide(
            uuid.uuid4(),
            status="rejected",
            reviewer_id="user-2",
        )
        session.execute.assert_awaited_once()


# ── ArtifactRepository ───────────────────────────────────────────────


class TestArtifactRepository:
    @pytest.mark.asyncio
    async def test_create(self) -> None:
        session = _mock_session()
        repo = ArtifactRepository(session)
        await repo.create(
            pipeline_run_id=uuid.uuid4(),
            path="src/main.py",
            content_type="text/python",
            size_bytes=123,
            storage_key="s3://bucket/key",
            language="python",
        )
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_for_run(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result
        repo = ArtifactRepository(session)
        result = await repo.list_for_run(uuid.uuid4())
        assert result == []


# ── UserRepository ───────────────────────────────────────────────────


class TestUserRepository:
    @pytest.mark.asyncio
    async def test_create(self) -> None:
        session = _mock_session()
        repo = UserRepository(session)
        await repo.create(username="alice", role="admin", api_key_hash="hash123")
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        session = _mock_session()
        session.get.return_value = MagicMock(username="bob")
        repo = UserRepository(session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_username(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        session.execute.return_value = mock_result
        repo = UserRepository(session)
        result = await repo.get_by_username("alice")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_api_key_hash(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result
        repo = UserRepository(session)
        result = await repo.get_by_api_key_hash("nonexistent")
        assert result is None
