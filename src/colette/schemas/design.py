"""Design → Implementation handoff schema (FR-ORC-020, §5)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from colette.schemas.base import HandoffSchema
from colette.schemas.common import (
    ADRRecord,
    ApprovalRecord,
    ComponentSpec,
    EndpointSpec,
    EntitySpec,
    TaskComplexity,
)


class ImplementationTask(BaseModel):
    """A single task in the implementation task graph (FR-DES-006)."""

    id: str
    description: str
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    dependencies: list[str] = Field(default_factory=list)
    assigned_agent: str | None = None


class DesignToImplementationHandoff(HandoffSchema):
    """Structured output of the Design stage consumed by Implementation."""

    source_stage: str = "design"
    target_stage: str = "implementation"
    schema_version: str = "1.0.0"

    # ── Architecture (FR-DES-001) ────────────────────────────────────
    architecture_summary: str = Field(description="Component decomposition and rationale.")
    tech_stack: dict[str, str] = Field(
        description="Mapping of role -> technology, e.g. {'frontend': 'Next.js'}."
    )

    # ── API (FR-DES-002) ─────────────────────────────────────────────
    openapi_spec: str = Field(description="Full OpenAPI 3.1 JSON string.")
    endpoints: list[EndpointSpec] = Field(default_factory=list)

    # ── Database (FR-DES-003) ────────────────────────────────────────
    db_entities: list[EntitySpec] = Field(default_factory=list)
    migration_strategy: str = ""

    # ── UI (FR-DES-004) ──────────────────────────────────────────────
    ui_components: list[ComponentSpec] = Field(default_factory=list)
    navigation_flows: list[str] = Field(default_factory=list)

    # ── Decisions (FR-DES-005) ───────────────────────────────────────
    adrs: list[ADRRecord] = Field(default_factory=list)

    # ── Security (FR-DES-007) ────────────────────────────────────────
    security_design: str = ""

    # ── Task graph (FR-DES-006) ──────────────────────────────────────
    tasks: list[ImplementationTask] = Field(default_factory=list)

    # ── Approval ─────────────────────────────────────────────────────
    approval: ApprovalRecord | None = None
