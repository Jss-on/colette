"""Per-agent, stage, and project cost tracking (NFR-OBS-002, NFR-OBS-003).

Calculates token costs from :class:`AgentInvocationRecord` using model-specific
pricing tables, aggregates costs at stage and pipeline levels, and detects
cost overruns against baselines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

if TYPE_CHECKING:
    from colette.observability.metrics import AgentInvocationRecord

logger = structlog.get_logger(__name__)


# ── Pricing ────────────────────────────────────────────────────────────


class ModelPrice(BaseModel, frozen=True):
    """Per-model pricing in USD per 1 million tokens.

    Attributes:
        input_per_million: Cost per 1M input (prompt) tokens.
        output_per_million: Cost per 1M output (completion) tokens.
    """

    input_per_million: float
    output_per_million: float


MODEL_PRICING: dict[str, ModelPrice] = {
    "claude-opus-4-6-20250610": ModelPrice(input_per_million=15.0, output_per_million=75.0),
    "claude-sonnet-4-6-20250514": ModelPrice(input_per_million=3.0, output_per_million=15.0),
    "claude-haiku-4-5-20251001": ModelPrice(input_per_million=0.80, output_per_million=4.0),
    "gpt-5.4": ModelPrice(input_per_million=2.50, output_per_million=10.0),
    "gpt-5.4-mini": ModelPrice(input_per_million=0.15, output_per_million=0.60),
}

_FALLBACK_MODEL = "claude-sonnet-4-6-20250514"


# ── Cost records ───────────────────────────────────────────────────────


class CostRecord(BaseModel, frozen=True):
    """Immutable cost breakdown for a single agent invocation.

    Attributes:
        agent_id: Unique identifier of the agent invocation.
        agent_role: Role name of the agent.
        model: Model name used for the invocation.
        input_tokens: Total prompt tokens consumed.
        output_tokens: Total completion tokens generated.
        input_cost: USD cost of input tokens.
        output_cost: USD cost of output tokens.
        total_cost: Sum of input_cost and output_cost.
        currency: Currency code (always ``"USD"``).
    """

    agent_id: str
    agent_role: str
    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    currency: str = "USD"


class CostAlert(BaseModel, frozen=True):
    """Alert raised when an agent's cost exceeds a baseline threshold.

    Attributes:
        agent_id: The agent whose cost exceeded the threshold.
        current_cost: Actual cost observed.
        baseline_cost: Expected baseline cost.
        multiplier: Factor by which baseline was exceeded.
        message: Human-readable alert description.
    """

    agent_id: str
    current_cost: float
    baseline_cost: float
    multiplier: float
    message: str


class StageCostSummary(BaseModel, frozen=True):
    """Aggregated cost summary for a single pipeline stage.

    Attributes:
        stage: Stage name (e.g. ``"requirements"``, ``"design"``).
        agent_costs: Individual agent cost records within the stage.
        total_cost: Sum of all agent costs in USD.
        token_count: Total tokens consumed across all agents.
    """

    stage: str
    agent_costs: list[CostRecord]
    total_cost: float
    token_count: int


class PipelineCostSummary(BaseModel, frozen=True):
    """Aggregated cost summary for an entire pipeline execution.

    Attributes:
        project_id: Project identifier.
        stage_summaries: Per-stage cost summaries.
        total_cost: Sum of all stage costs in USD.
        total_tokens: Total tokens consumed across all stages.
    """

    project_id: str
    stage_summaries: list[StageCostSummary]
    total_cost: float
    total_tokens: int


# ── Calculation functions ──────────────────────────────────────────────


def calculate_cost(record: AgentInvocationRecord) -> CostRecord:
    """Calculate the USD cost of an agent invocation.

    Looks up model pricing from :data:`MODEL_PRICING`.  Falls back to
    Sonnet pricing when the model is not found.

    Args:
        record: Immutable agent invocation record with token counts.

    Returns:
        A frozen :class:`CostRecord` with computed costs.
    """
    price = MODEL_PRICING.get(record.model)
    if price is None:
        logger.warning(
            "model_pricing_not_found",
            model=record.model,
            fallback=_FALLBACK_MODEL,
        )
        price = MODEL_PRICING[_FALLBACK_MODEL]

    input_cost = (record.input_tokens / 1_000_000) * price.input_per_million
    output_cost = (record.output_tokens / 1_000_000) * price.output_per_million

    return CostRecord(
        agent_id=record.agent_id,
        agent_role=record.agent_role,
        model=record.model,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=input_cost + output_cost,
    )


def aggregate_stage_costs(stage: str, records: list[AgentInvocationRecord]) -> StageCostSummary:
    """Aggregate costs for all agent invocations in a pipeline stage.

    Args:
        stage: Stage name (e.g. ``"implementation"``).
        records: Agent invocation records belonging to this stage.

    Returns:
        A frozen :class:`StageCostSummary`.
    """
    agent_costs = [calculate_cost(r) for r in records]
    total_cost = sum(c.total_cost for c in agent_costs)
    token_count = sum(r.total_tokens for r in records)

    logger.info(
        "stage_cost_aggregated",
        stage=stage,
        agent_count=len(agent_costs),
        total_cost=round(total_cost, 6),
        token_count=token_count,
    )

    return StageCostSummary(
        stage=stage,
        agent_costs=agent_costs,
        total_cost=total_cost,
        token_count=token_count,
    )


def aggregate_pipeline_costs(
    project_id: str, stage_summaries: list[StageCostSummary]
) -> PipelineCostSummary:
    """Aggregate costs across all pipeline stages for a project.

    Args:
        project_id: Project identifier.
        stage_summaries: Per-stage cost summaries.

    Returns:
        A frozen :class:`PipelineCostSummary`.
    """
    total_cost = sum(s.total_cost for s in stage_summaries)
    total_tokens = sum(s.token_count for s in stage_summaries)

    logger.info(
        "pipeline_cost_aggregated",
        project_id=project_id,
        stage_count=len(stage_summaries),
        total_cost=round(total_cost, 6),
        total_tokens=total_tokens,
    )

    return PipelineCostSummary(
        project_id=project_id,
        stage_summaries=stage_summaries,
        total_cost=total_cost,
        total_tokens=total_tokens,
    )


def check_cost_overrun(
    current: CostRecord,
    baseline_cost: float,
    multiplier: float = 2.0,
) -> CostAlert | None:
    """Check whether an agent's cost exceeds a baseline threshold.

    Args:
        current: The cost record to evaluate.
        baseline_cost: Expected baseline cost in USD.
        multiplier: Factor above baseline that triggers an alert (default 2.0).

    Returns:
        A :class:`CostAlert` if the threshold is exceeded, else ``None``.
    """
    threshold = baseline_cost * multiplier
    if current.total_cost > threshold:
        alert = CostAlert(
            agent_id=current.agent_id,
            current_cost=current.total_cost,
            baseline_cost=baseline_cost,
            multiplier=multiplier,
            message=(
                f"Agent {current.agent_id} cost ${current.total_cost:.4f} "
                f"exceeds {multiplier}x baseline ${baseline_cost:.4f} "
                f"(threshold ${threshold:.4f})"
            ),
        )
        logger.warning(
            "cost_overrun_detected",
            agent_id=current.agent_id,
            current_cost=current.total_cost,
            baseline_cost=baseline_cost,
            multiplier=multiplier,
        )
        return alert
    return None
