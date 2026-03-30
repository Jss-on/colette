"""Confidence-gated memory writes (NFR-SEC-010).

Evaluates whether an agent-requested memory write should be allowed based on
the content importance level and the agent's reported confidence.  High and
critical writes always trigger audit logging.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class MemoryWriteRequest(BaseModel):
    """An agent's request to persist data to the memory layer."""

    model_config = {"frozen": True}

    content: str = Field(description="Text content to write.")
    importance: str = Field(
        description="Importance tier: 'low', 'medium', 'high', or 'critical'.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Agent's self-reported confidence in the content.",
    )
    source_agent: str = Field(description="Identifier of the requesting agent.")
    project_id: str = Field(description="Project this write belongs to.")


class MemoryWriteDecision(BaseModel):
    """Outcome of a memory write evaluation."""

    model_config = {"frozen": True}

    allowed: bool = Field(description="Whether the write is permitted.")
    requires_audit: bool = Field(
        description="Whether the write must be recorded in the audit log.",
    )
    reason: str = Field(description="Human-readable rationale for the decision.")


# ---------------------------------------------------------------------------
# Importance tiers that always require audit
# ---------------------------------------------------------------------------

_AUDIT_REQUIRED_TIERS: frozenset[str] = frozenset({"high", "critical"})

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_memory_write(
    request: MemoryWriteRequest,
    *,
    confidence_threshold: float = 0.70,
) -> MemoryWriteDecision:
    """Decide whether *request* should be allowed.

    Decision matrix:

    +-----------+-------------------+-------------------------------------------+
    | Importance| Confidence >= thr | Result                                    |
    +-----------+-------------------+-------------------------------------------+
    | high/crit | yes               | allowed=True, requires_audit=True         |
    | high/crit | no                | allowed=False, requires_audit=True        |
    | low/med   | yes               | allowed=True, requires_audit=False        |
    | low/med   | no                | allowed=False, requires_audit=False       |
    +-----------+-------------------+-------------------------------------------+
    """
    importance = request.importance.lower()
    meets_threshold = request.confidence >= confidence_threshold
    requires_audit = importance in _AUDIT_REQUIRED_TIERS

    if meets_threshold:
        return MemoryWriteDecision(
            allowed=True,
            requires_audit=requires_audit,
            reason=(
                f"Confidence {request.confidence:.2f} meets threshold "
                f"{confidence_threshold:.2f} for '{importance}' importance."
            ),
        )

    return MemoryWriteDecision(
        allowed=False,
        requires_audit=requires_audit,
        reason=(
            f"Confidence {request.confidence:.2f} is below threshold "
            f"{confidence_threshold:.2f} for '{importance}' importance. "
            "Write rejected."
        ),
    )
