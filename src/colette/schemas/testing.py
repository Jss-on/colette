"""Testing → Deployment handoff schema (FR-ORC-020, §7)."""

from __future__ import annotations

from pydantic import Field

from colette.schemas.base import HandoffSchema
from colette.schemas.common import SecurityFinding, SuiteResult


class TestingToDeploymentHandoff(HandoffSchema):
    """Structured output of the Testing stage consumed by Deployment."""

    source_stage: str = "testing"
    target_stage: str = "deployment"
    schema_version: str = "1.0.0"

    # ── Test results (FR-TST-008) ────────────────────────────────────
    test_results: list[SuiteResult] = Field(default_factory=list)
    overall_line_coverage: float = Field(ge=0.0, le=100.0, default=0.0)
    overall_branch_coverage: float = Field(ge=0.0, le=100.0, default=0.0)

    # ── Security (FR-TST-006/007) ────────────────────────────────────
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    dependency_vulnerabilities: list[SecurityFinding] = Field(default_factory=list)

    # ── Contract testing (FR-TST-004) ────────────────────────────────
    contract_tests_passed: bool = False
    contract_deviations: list[str] = Field(default_factory=list)

    # ── Readiness (FR-TST-008) ───────────────────────────────────────
    deploy_readiness_score: int = Field(
        ge=0,
        le=100,
        default=0,
        description="0-100 score summarizing overall test quality.",
    )
    blocking_issues: list[str] = Field(default_factory=list)

    # ── Git ref ──────────────────────────────────────────────────────
    git_ref: str = Field(default="", description="Tested branch or commit SHA.")
