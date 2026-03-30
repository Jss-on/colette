"""Shared sub-models used across multiple handoff schemas (FR-ORC-020/022)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ── Enums ────────────────────────────────────────────────────────────────


class Priority(StrEnum):
    MUST = "MUST"
    SHOULD = "SHOULD"
    COULD = "COULD"


class ApprovalTier(StrEnum):
    T0_CRITICAL = "T0"
    T1_HIGH = "T1"
    T2_MODERATE = "T2"
    T3_ROUTINE = "T3"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    AUTO_APPROVED = "auto_approved"
    TIMED_OUT = "timed_out"


class StageName(StrEnum):
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED_BY_GATE = "blocked_by_gate"
    AWAITING_APPROVAL = "awaiting_approval"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class TaskComplexity(StrEnum):
    SMALL = "S"
    MEDIUM = "M"
    LARGE = "L"
    EXTRA_LARGE = "XL"


# ── Shared Sub-models ────────────────────────────────────────────────────


class UserStory(BaseModel):
    """A user story with acceptance criteria (FR-REQ-007)."""

    id: str = Field(description="Unique ID in format US-{STAGE}-{NNN}.")
    title: str
    persona: str = Field(description="As a <persona>...")
    goal: str = Field(description="I want to <goal>...")
    benefit: str = Field(description="So that <benefit>...")
    acceptance_criteria: list[str] = Field(min_length=1)
    priority: Priority = Priority.MUST


class NFRSpec(BaseModel):
    """A non-functional requirement specification."""

    id: str
    category: str = Field(description="E.g. performance, security, scalability.")
    description: str
    metric: str | None = None
    target: str | None = None
    priority: Priority = Priority.MUST


class TechConstraint(BaseModel):
    """A technology or design constraint."""

    id: str
    description: str
    rationale: str


class ApprovalRecord(BaseModel):
    """Records a human approval decision (FR-HIL-003)."""

    reviewer_id: str
    status: ApprovalStatus
    tier: ApprovalTier
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    comments: str = ""
    modifications: dict[str, str] = Field(default_factory=dict)


class QualityGateResult(BaseModel):
    """Result of a quality gate evaluation (Section 12)."""

    gate_name: str
    passed: bool
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    criteria_results: dict[str, bool] = Field(default_factory=dict)
    failure_reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FileDiff(BaseModel):
    """A file change record for implementation handoffs."""

    path: str
    action: str = Field(description="added | modified | deleted")
    language: str | None = None
    lines_added: int = 0
    lines_removed: int = 0


class EndpointSpec(BaseModel):
    """A REST API endpoint specification."""

    method: str = Field(description="HTTP method: GET, POST, PUT, DELETE, PATCH.")
    path: str
    summary: str = ""
    request_schema: str | None = None
    response_schema: str | None = None
    auth_required: bool = True


class EntitySpec(BaseModel):
    """A database entity specification."""

    name: str
    fields: list[dict[str, str]] = Field(description="List of {name, type, constraints} dicts.")
    indexes: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)


class ComponentSpec(BaseModel):
    """A UI component specification."""

    name: str
    description: str = ""
    props: list[dict[str, str]] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    route: str | None = None


class ADRRecord(BaseModel):
    """Architecture Decision Record (FR-DES-005)."""

    id: str
    title: str
    status: str = "proposed"
    context: str = ""
    decision: str = ""
    alternatives: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)


class SecurityFinding(BaseModel):
    """A security scan finding."""

    id: str
    severity: Severity
    category: str
    description: str
    location: str = ""
    recommendation: str = ""


class SuiteResult(BaseModel):
    """Aggregated test results for a test category."""

    category: str = Field(description="unit | integration | e2e | security | contract")
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    line_coverage: float | None = Field(default=None, ge=0.0, le=100.0)
    branch_coverage: float | None = Field(default=None, ge=0.0, le=100.0)


class DeploymentTarget(BaseModel):
    """Deployment environment specification."""

    environment: str = Field(description="staging | production")
    url: str | None = None
    health_check_url: str | None = None
    replicas: int = 1
    resource_limits: dict[str, str] = Field(default_factory=dict)


class GeneratedFile(BaseModel, frozen=True):
    """A single generated source file (FR-IMP-001/002/003)."""

    path: str = Field(description="Relative file path.")
    content: str = Field(description="Full file content.")
    language: str = Field(description="Programming language (e.g. 'python', 'typescript').")
