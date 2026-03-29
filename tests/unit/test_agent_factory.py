"""Tests for agent factory (FR-ORC-010/011/012/016)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from colette.config import Settings
from colette.orchestrator.agent_factory import (
    AgentInstance,
    CircuitBreakerOpenError,
    create_agent,
    invoke_agent,
)
from colette.orchestrator.circuit_breaker import CircuitBreaker, CircuitState
from colette.schemas.agent_config import AgentConfig, AgentRole, ModelTier


def _make_config(**overrides: object) -> AgentConfig:
    defaults: dict[str, object] = {
        "role": AgentRole.BACKEND_DEV,
        "system_prompt": "You are a backend developer.",
        "model_tier": ModelTier.EXECUTION,
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)  # type: ignore[arg-type]


class TestCreateAgent:
    @patch("colette.orchestrator.agent_factory.create_react_agent")
    @patch("colette.orchestrator.agent_factory.create_chat_model")
    def test_returns_agent_instance(
        self, mock_chat: MagicMock, mock_react: MagicMock
    ) -> None:
        mock_chat.return_value = MagicMock()
        mock_react.return_value = MagicMock()

        config = _make_config()
        settings = Settings()
        agent = create_agent(config, settings=settings)

        assert isinstance(agent, AgentInstance)
        assert agent.role == AgentRole.BACKEND_DEV
        assert agent.config is config
        assert agent.agent_id  # non-empty

    @patch("colette.orchestrator.agent_factory.create_react_agent")
    @patch("colette.orchestrator.agent_factory.create_chat_model")
    def test_uses_llm_gateway(
        self, mock_chat: MagicMock, mock_react: MagicMock
    ) -> None:
        mock_chat.return_value = MagicMock()
        mock_react.return_value = MagicMock()

        config = _make_config()
        settings = Settings()
        create_agent(config, settings=settings)

        mock_chat.assert_called_once()

    @patch("colette.orchestrator.agent_factory.create_react_agent")
    @patch("colette.orchestrator.agent_factory.create_chat_model")
    def test_passes_tools_to_react_agent(
        self, mock_chat: MagicMock, mock_react: MagicMock
    ) -> None:
        mock_chat.return_value = MagicMock()
        mock_react.return_value = MagicMock()

        tool = MagicMock()
        tool.name = "filesystem"
        config = _make_config()
        create_agent(config, settings=Settings(), tools=[tool])

        _, kwargs = mock_react.call_args
        assert tool in kwargs.get("tools", [])


class TestInvokeAgent:
    def _make_agent(self, **overrides: object) -> AgentInstance:
        config = _make_config(**overrides)
        graph = MagicMock()
        graph.ainvoke = AsyncMock(return_value={"messages": [MagicMock()]})
        return AgentInstance(
            agent_id="test-agent-1",
            role=config.role,
            graph=graph,
            config=config,
            circuit_breaker=CircuitBreaker(agent_role=str(config.role)),
        )

    @pytest.mark.asyncio
    async def test_sets_recursion_limit(self) -> None:
        agent = self._make_agent(max_iterations=10)
        await invoke_agent(agent, [("user", "hello")])

        call_args = agent.graph.ainvoke.call_args
        config = call_args[1].get("config", call_args[0][1] if len(call_args[0]) > 1 else {})
        assert config.get("recursion_limit") == 10

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(self) -> None:
        agent = self._make_agent()
        # Force circuit breaker open
        cb = agent.circuit_breaker
        for _ in range(3):
            cb = cb.record_failure()
        agent = AgentInstance(
            agent_id=agent.agent_id,
            role=agent.role,
            graph=agent.graph,
            config=agent.config,
            circuit_breaker=cb,
        )

        with pytest.raises(CircuitBreakerOpenError):
            await invoke_agent(agent, [("user", "hello")])

    @pytest.mark.asyncio
    async def test_timeout_raises(self) -> None:
        agent = self._make_agent(timeout_seconds=1)

        async def slow_invoke(*args: object, **kwargs: object) -> dict:
            await asyncio.sleep(5)
            return {"messages": []}

        agent.graph.ainvoke = slow_invoke  # type: ignore[assignment]

        with pytest.raises(TimeoutError):
            await invoke_agent(agent, [("user", "hello")], timeout=1)

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self) -> None:
        agent = self._make_agent()
        result = await invoke_agent(agent, [("user", "hello")])
        assert "messages" in result

    @pytest.mark.asyncio
    async def test_callback_handler_attached(self) -> None:
        agent = self._make_agent()
        await invoke_agent(agent, [("user", "hello")])

        call_args = agent.graph.ainvoke.call_args
        config = call_args[1].get("config", call_args[0][1] if len(call_args[0]) > 1 else {})
        callbacks = config.get("callbacks", [])
        assert len(callbacks) >= 1
