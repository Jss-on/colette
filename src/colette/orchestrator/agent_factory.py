"""Agent factory: create and invoke ephemeral agents (FR-ORC-010/011/012/016).

``create_agent()`` wraps LangGraph's ``create_react_agent()`` with
the Colette LLM gateway, circuit breaker, and observability callback.
``invoke_agent()`` runs the agent with timeout, iteration limits,
and error recovery.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from langgraph.prebuilt import create_react_agent

from colette.llm.gateway import create_chat_model
from colette.observability.callbacks import ColletteCallbackHandler
from colette.observability.metrics import Outcome
from colette.orchestrator.circuit_breaker import CircuitBreaker

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from colette.config import Settings
    from colette.schemas.agent_config import AgentConfig, AgentRole

logger = structlog.get_logger(__name__)


class CircuitBreakerOpenError(RuntimeError):
    """Raised when the circuit breaker is open for an agent."""


@dataclass
class AgentInstance:
    """A created agent ready for invocation."""

    agent_id: str
    role: AgentRole
    graph: Any  # CompiledGraph from LangGraph
    config: AgentConfig
    circuit_breaker: CircuitBreaker


def create_agent(
    agent_config: AgentConfig,
    *,
    tools: list[BaseTool] | None = None,
    settings: Settings | None = None,
) -> AgentInstance:
    """Create an ephemeral agent instance (FR-ORC-010).

    The agent is configured with:
    - LLM model from the gateway (with fallback chain)
    - Tool list (access-controlled)
    - Circuit breaker instance
    - Fresh ID for observability
    """
    if settings is None:
        from colette.config import Settings as _Settings

        settings = _Settings()

    model = create_chat_model(agent_config, settings=settings)
    agent_tools = tools or []

    graph = create_react_agent(
        model=model,
        tools=agent_tools,
    )

    agent_id = f"{agent_config.role}-{uuid.uuid4().hex[:8]}"

    return AgentInstance(
        agent_id=agent_id,
        role=agent_config.role,
        graph=graph,
        config=agent_config,
        circuit_breaker=CircuitBreaker(
            agent_role=str(agent_config.role),
            threshold=agent_config.circuit_breaker_threshold,
            window_seconds=agent_config.circuit_breaker_window_seconds,
            cooldown_seconds=agent_config.circuit_breaker_cooldown_seconds,
        ),
    )


async def invoke_agent(
    agent: AgentInstance,
    messages: list[Any],
    *,
    thread_id: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Invoke an agent with timeout, iteration limit, and circuit breaker.

    - Checks circuit breaker before running (FR-ORC-018)
    - Sets ``recursion_limit`` from config (FR-ORC-011)
    - Wraps with ``asyncio.timeout`` (FR-ORC-012)
    - Attaches observability callback (FR-ORC-015)

    Returns the agent's output state dict.
    """
    # ── Circuit breaker check ──────────────────────────────────────
    if agent.circuit_breaker.is_open:
        logger.warning(
            "circuit_breaker_open",
            agent_id=agent.agent_id,
            agent_role=str(agent.role),
        )
        raise CircuitBreakerOpenError(f"Circuit breaker open for {agent.agent_id}")

    # ── Build run config ───────────────────────────────────────────
    callback = ColletteCallbackHandler(
        agent_id=agent.agent_id,
        agent_role=str(agent.role),
        model=str(agent.config.model_tier),
    )

    run_config: dict[str, Any] = {
        "recursion_limit": agent.config.max_iterations,
        "callbacks": [callback],
    }
    if thread_id:
        run_config["configurable"] = {"thread_id": thread_id}

    effective_timeout = timeout or agent.config.timeout_seconds
    start = time.monotonic()

    # ── Execute with timeout ───────────────────────────────────────
    try:
        async with asyncio.timeout(effective_timeout):
            result = await agent.graph.ainvoke(
                {"messages": messages},
                config=run_config,
            )
    except TimeoutError:
        duration_ms = (time.monotonic() - start) * 1000
        callback.build_record(outcome=Outcome.TIMEOUT, duration_ms=duration_ms)
        logger.warning(
            "agent_timeout",
            agent_id=agent.agent_id,
            timeout_seconds=effective_timeout,
        )
        agent.circuit_breaker = agent.circuit_breaker.record_failure()
        raise
    except Exception:
        duration_ms = (time.monotonic() - start) * 1000
        callback.build_record(outcome=Outcome.FAILURE, duration_ms=duration_ms)
        agent.circuit_breaker = agent.circuit_breaker.record_failure()
        raise

    duration_ms = (time.monotonic() - start) * 1000
    record = callback.build_record(outcome=Outcome.SUCCESS, duration_ms=duration_ms)
    logger.info(
        "agent_invocation_complete",
        agent_id=agent.agent_id,
        duration_ms=round(duration_ms, 2),
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        tool_calls=len(record.tool_calls),
    )
    agent.circuit_breaker = agent.circuit_breaker.record_success()

    return result  # type: ignore[no-any-return]
