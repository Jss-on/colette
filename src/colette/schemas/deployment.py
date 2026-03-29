"""Deployment → Monitoring handoff schema (FR-ORC-020, §8)."""

from __future__ import annotations

from pydantic import Field

from colette.schemas.base import HandoffSchema
from colette.schemas.common import ApprovalRecord, DeploymentTarget


class DeploymentToMonitoringHandoff(HandoffSchema):
    """Structured output of the Deployment stage consumed by Monitoring."""

    source_stage: str = "deployment"
    target_stage: str = "monitoring"
    schema_version: str = "1.0.0"

    # ── Deployment info ──────────────────────────────────────────────
    deployment_id: str = Field(description="Unique deployment identifier.")
    targets: list[DeploymentTarget] = Field(default_factory=list)

    # ── Artifacts ────────────────────────────────────────────────────
    docker_images: list[str] = Field(
        default_factory=list,
        description="List of image:tag strings pushed to registry.",
    )
    ci_pipeline_url: str = ""
    git_ref: str = ""

    # ── Rollback ─────────────────────────────────────────────────────
    previous_deployment_id: str | None = None
    rollback_command: str = ""

    # ── SLO targets (FR-MON-008) ─────────────────────────────────────
    slo_targets: dict[str, str] = Field(
        default_factory=dict,
        description="E.g. {'availability': '99.9%', 'p99_latency': '500ms'}.",
    )

    # ── Approval (FR-DEP-006) ────────────────────────────────────────
    staging_approval: ApprovalRecord | None = None
    production_approval: ApprovalRecord | None = None
