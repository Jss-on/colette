"""Agent configuration model (FR-ORC-010/017, FR-MEM-004)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from colette.schemas.common import ApprovalTier

MAX_TOOLS_PER_AGENT = 5


class AgentRole(StrEnum):
    """Predefined agent roles matching the architecture spec."""

    # Orchestrator
    PROJECT_ORCHESTRATOR = "project_orchestrator"

    # Stage supervisors
    REQUIREMENTS_SUPERVISOR = "requirements_supervisor"
    DESIGN_SUPERVISOR = "design_supervisor"
    IMPLEMENTATION_SUPERVISOR = "implementation_supervisor"
    TESTING_SUPERVISOR = "testing_supervisor"
    DEPLOYMENT_SUPERVISOR = "deployment_supervisor"
    MONITORING_SUPERVISOR = "monitoring_supervisor"

    # Specialists
    REQUIREMENTS_ANALYST = "requirements_analyst"
    DOMAIN_RESEARCHER = "domain_researcher"
    SYSTEM_ARCHITECT = "system_architect"
    API_DESIGNER = "api_designer"
    UI_UX_DESIGNER = "ui_ux_designer"
    FRONTEND_DEV = "frontend_dev"
    BACKEND_DEV = "backend_dev"
    DB_ENGINEER = "db_engineer"
    UNIT_TESTER = "unit_tester"
    INTEGRATION_TESTER = "integration_tester"
    SECURITY_SCANNER = "security_scanner"
    CICD_ENGINEER = "cicd_engineer"
    INFRA_ENGINEER = "infra_engineer"
    OBSERVABILITY_AGENT = "observability_agent"
    INCIDENT_RESPONSE = "incident_response"


class ModelTier(StrEnum):
    """Model assignment tiers matching the architecture spec."""

    PLANNING = "planning"  # Opus — orchestrator, design supervisor, architect
    EXECUTION = "execution"  # Sonnet — all other agents
    VALIDATION = "validation"  # Haiku — scanners, validators


@dataclass(frozen=True)
class ContextBudgetAllocation:
    """Token budget allocation percentages (FR-MEM-004).

    All values are fractions (0.0-1.0) that must sum to 1.0.
    """

    system_prompt: float = 0.10
    tools: float = 0.15
    retrieved_context: float = 0.35
    history: float = 0.15
    output: float = 0.25

    def __post_init__(self) -> None:
        total = (
            self.system_prompt + self.tools + self.retrieved_context + self.history + self.output
        )
        if abs(total - 1.0) > 0.01:
            msg = f"Budget allocation must sum to 1.0, got {total:.2f}"
            raise ValueError(msg)


# Default allocations per agent tier
SUPERVISOR_BUDGET = ContextBudgetAllocation()
SPECIALIST_BUDGET = ContextBudgetAllocation(
    system_prompt=0.10,
    tools=0.15,
    retrieved_context=0.40,
    history=0.15,
    output=0.20,
)
VALIDATOR_BUDGET = ContextBudgetAllocation(
    system_prompt=0.15,
    tools=0.15,
    retrieved_context=0.35,
    history=0.10,
    output=0.25,
)


class AgentConfig(BaseModel):
    """Configuration for a single agent instance (FR-ORC-010).

    Loaded fresh on each agent instantiation to support hot-swap (FR-ORC-016).
    """

    role: AgentRole
    system_prompt: str = Field(min_length=1)
    model_tier: ModelTier = ModelTier.EXECUTION
    model_name: str | None = Field(
        default=None,
        description="Override the model resolved from model_tier.",
    )

    # ── Tools (FR-ORC-017) ───────────────────────────────────────────
    tool_names: list[str] = Field(
        default_factory=list,
        description="Names of BaseTool instances this agent may use.",
    )

    @field_validator("tool_names")
    @classmethod
    def _enforce_tool_limit(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_TOOLS_PER_AGENT:
            msg = f"Agent may use at most {MAX_TOOLS_PER_AGENT} tools, got {len(v)}: {v}"
            raise ValueError(msg)
        return v

    # ── Context budget (FR-MEM-004) ──────────────────────────────────
    context_budget_tokens: int = Field(
        default=60_000,
        description="Max tokens for this agent's context window.",
    )

    # ── Execution limits (FR-ORC-011/012) ────────────────────────────
    max_iterations: int = Field(default=25, ge=1)
    timeout_seconds: int = Field(default=600, ge=1)

    # ── Approval tier (FR-HIL-001) ───────────────────────────────────
    approval_tier: ApprovalTier = ApprovalTier.T3_ROUTINE

    # ── Circuit breaker (FR-ORC-018) ─────────────────────────────────
    circuit_breaker_threshold: int = Field(
        default=3,
        description="Consecutive failures before circuit opens.",
    )
    circuit_breaker_window_seconds: int = Field(default=300)
    circuit_breaker_cooldown_seconds: int = Field(default=120)
