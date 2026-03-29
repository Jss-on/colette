"""Tests for notification dispatch."""

from __future__ import annotations

import pytest

from colette.config import Settings
from colette.human.models import ApprovalRequest
from colette.human.notifications import InAppChannel, notify_reviewers
from colette.schemas.common import ApprovalTier


@pytest.fixture
def sample_request() -> ApprovalRequest:
    return ApprovalRequest(
        request_id="r1",
        project_id="p1",
        stage="deployment",
        tier=ApprovalTier.T0_CRITICAL,
        context_summary="Deploy to prod",
        proposed_action="Run deploy",
    )


class TestInAppChannel:
    @pytest.mark.asyncio
    async def test_send_returns_true(self, sample_request: ApprovalRequest) -> None:
        ch = InAppChannel()
        assert await ch.send(sample_request) is True


class TestNotifyReviewers:
    @pytest.mark.asyncio
    async def test_dispatches_to_in_app(self, sample_request: ApprovalRequest) -> None:
        settings = Settings(notification_channels=["in_app"])
        results = await notify_reviewers(sample_request, settings)
        assert results == [True]

    @pytest.mark.asyncio
    async def test_empty_channels(self, sample_request: ApprovalRequest) -> None:
        settings = Settings(notification_channels=[])
        results = await notify_reviewers(sample_request, settings)
        assert results == []
