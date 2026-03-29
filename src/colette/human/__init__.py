"""Human-in-the-loop approval system (FR-HIL-*)."""

from colette.human.approval import (
    apply_modifications,
    create_approval_request,
    determine_approval_action,
)
from colette.human.confidence import (
    evaluate_confidence,
    extract_confidence_from_response,
)
from colette.human.feedback import (
    FeedbackRecord,
    compute_calibration_drift,
    create_feedback_record,
)
from colette.human.models import (
    ApprovalDecision,
    ApprovalRequest,
    ConfidenceResult,
)
from colette.human.notifications import notify_reviewers
from colette.human.sla import (
    SLARecord,
    build_sla_report,
    check_breach,
    compute_deadline,
)

__all__ = [
    "ApprovalDecision",
    "ApprovalRequest",
    "ConfidenceResult",
    "FeedbackRecord",
    "SLARecord",
    "apply_modifications",
    "build_sla_report",
    "check_breach",
    "compute_calibration_drift",
    "compute_deadline",
    "create_approval_request",
    "create_feedback_record",
    "determine_approval_action",
    "evaluate_confidence",
    "extract_confidence_from_response",
    "notify_reviewers",
]
