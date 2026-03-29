"""Tests for HIL data models."""

from __future__ import annotations

from colette.human.models import ApprovalDecision, ApprovalRequest, ConfidenceResult
from colette.schemas.common import ApprovalStatus, ApprovalTier


class TestApprovalRequest:
    def test_create_minimal(self) -> None:
        req = ApprovalRequest(
            request_id="r1",
            project_id="p1",
            stage="requirements",
            tier=ApprovalTier.T0_CRITICAL,
            context_summary="Test",
            proposed_action="Deploy",
        )
        assert req.request_id == "r1"
        assert req.tier == ApprovalTier.T0_CRITICAL

    def test_is_frozen(self) -> None:
        req = ApprovalRequest(
            request_id="r1",
            project_id="p1",
            stage="design",
            tier=ApprovalTier.T1_HIGH,
            context_summary="Test",
            proposed_action="Action",
        )
        assert req.model_config.get("frozen") is True


class TestApprovalDecision:
    def test_approved_decision(self) -> None:
        dec = ApprovalDecision(
            request_id="r1",
            reviewer_id="user1",
            status=ApprovalStatus.APPROVED,
        )
        assert dec.status == ApprovalStatus.APPROVED
        assert dec.modifications == {}

    def test_modified_decision(self) -> None:
        dec = ApprovalDecision(
            request_id="r1",
            reviewer_id="user1",
            status=ApprovalStatus.MODIFIED,
            modifications={"completeness_score": 0.95},
        )
        assert dec.modifications["completeness_score"] == 0.95


class TestConfidenceResult:
    def test_escalate(self) -> None:
        cr = ConfidenceResult(score=0.40, action="escalate")
        assert cr.action == "escalate"

    def test_auto_approve(self) -> None:
        cr = ConfidenceResult(score=0.90, action="auto_approve")
        assert cr.action == "auto_approve"
