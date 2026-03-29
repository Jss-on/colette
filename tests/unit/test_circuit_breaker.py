"""Tests for circuit breaker (FR-ORC-018)."""

from __future__ import annotations

import time

from colette.orchestrator.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    def _make_breaker(self, **overrides: object) -> CircuitBreaker:
        defaults: dict[str, object] = {
            "agent_role": "test_agent",
            "threshold": 3,
            "window_seconds": 300,
            "cooldown_seconds": 120,
        }
        defaults.update(overrides)
        return CircuitBreaker(**defaults)  # type: ignore[arg-type]

    def test_initial_state_is_closed(self) -> None:
        cb = self._make_breaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_open is False

    def test_stays_closed_below_threshold(self) -> None:
        cb = self._make_breaker()
        cb = cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb = cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_opens_at_threshold(self) -> None:
        cb = self._make_breaker()
        for _ in range(3):
            cb = cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_open is True

    def test_stays_closed_if_failures_outside_window(self) -> None:
        cb = self._make_breaker(window_seconds=1)
        cb = cb.record_failure()
        cb = cb.record_failure()
        # Simulate old timestamps by directly constructing
        now = time.monotonic()
        old_timestamps = (now - 10.0, now - 10.0)
        cb = CircuitBreaker(
            agent_role="test_agent",
            threshold=3,
            window_seconds=1,
            cooldown_seconds=120,
            failure_timestamps=old_timestamps + (now,),
        )
        # Only 1 failure within window — still closed
        assert cb.state == CircuitState.CLOSED

    def test_half_open_after_cooldown(self) -> None:
        cb = self._make_breaker(cooldown_seconds=1)
        for _ in range(3):
            cb = cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Simulate cooldown expired by constructing with old opened_at
        now = time.monotonic()
        cb = CircuitBreaker(
            agent_role="test_agent",
            threshold=3,
            window_seconds=300,
            cooldown_seconds=1,
            failure_timestamps=(now, now, now),
            opened_at=now - 2.0,
        )
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_resets_to_closed(self) -> None:
        cb = self._make_breaker()
        for _ in range(3):
            cb = cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb = cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_open is False

    def test_immutability(self) -> None:
        original = self._make_breaker()
        after_failure = original.record_failure()
        # Original unchanged
        assert original.failure_timestamps == ()
        assert len(after_failure.failure_timestamps) == 1

    def test_failure_count_in_window(self) -> None:
        cb = self._make_breaker()
        cb = cb.record_failure()
        cb = cb.record_failure()
        assert cb.failure_count_in_window == 2
