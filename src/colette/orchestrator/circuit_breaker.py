"""Circuit breaker for agent invocations (FR-ORC-018).

When an agent fails ``threshold`` times within ``window_seconds``,
the breaker opens and blocks further invocations until ``cooldown_seconds``
have elapsed.  All mutations return a **new** instance (immutable).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(StrEnum):
    """Circuit breaker states.

    Attributes:
        CLOSED: Normal operation -- requests pass through.
        OPEN: Breaker tripped -- all requests are rejected immediately.
        HALF_OPEN: Cooldown expired -- one probe request is allowed.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitBreaker:
    """Immutable circuit breaker with rolling-window failure tracking.

    All mutations return a **new** instance.  This makes the breaker
    safe to share across async tasks without locks.

    Attributes:
        agent_role: Identifier of the agent this breaker protects.
        threshold: Consecutive failures within *window_seconds* before opening.
        window_seconds: Rolling window for failure counting.
        cooldown_seconds: Time the breaker stays open before transitioning to half-open.
        failure_timestamps: Monotonic timestamps of recent failures.
        opened_at: Monotonic timestamp when the breaker entered OPEN state.
    """

    agent_role: str
    threshold: int = 3
    window_seconds: int = 300
    cooldown_seconds: int = 120

    failure_timestamps: tuple[float, ...] = field(default_factory=tuple)
    opened_at: float | None = None

    # ── Derived state ───────────────────────────────────────────────

    @property
    def failure_count_in_window(self) -> int:
        """Count failures within the rolling window.

        Returns:
            Number of failures recorded in the last *window_seconds*.
        """
        cutoff = time.monotonic() - self.window_seconds
        return sum(1 for ts in self.failure_timestamps if ts > cutoff)

    @property
    def state(self) -> CircuitState:
        """Current state derived from open timestamp and cooldown.

        Returns:
            :attr:`CircuitState.OPEN` if within cooldown,
            :attr:`CircuitState.HALF_OPEN` if cooldown expired,
            :attr:`CircuitState.CLOSED` otherwise.
        """
        if self.opened_at is not None:
            elapsed = time.monotonic() - self.opened_at
            if elapsed >= self.cooldown_seconds:
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN
        return CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Whether the breaker is currently blocking requests.

        Returns:
            ``True`` if state is OPEN (not HALF_OPEN or CLOSED).
        """
        return self.state == CircuitState.OPEN

    # ── Mutations (return new instance) ─────────────────────────────

    def record_failure(self) -> CircuitBreaker:
        """Record a failure and open the breaker if threshold is reached.

        Returns:
            A new :class:`CircuitBreaker` with the failure recorded.
            If the threshold is reached, the breaker transitions to OPEN.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        recent = tuple(ts for ts in self.failure_timestamps if ts > cutoff)
        updated = (*recent, now)

        opened = self.opened_at
        if len(updated) >= self.threshold and opened is None:
            opened = now
            logger.warning(
                "circuit_breaker_opened",
                agent_role=self.agent_role,
                failures=len(updated),
                threshold=self.threshold,
            )
        else:
            logger.info(
                "circuit_breaker_failure_recorded",
                agent_role=self.agent_role,
                failures_in_window=len(updated),
                threshold=self.threshold,
            )

        return CircuitBreaker(
            agent_role=self.agent_role,
            threshold=self.threshold,
            window_seconds=self.window_seconds,
            cooldown_seconds=self.cooldown_seconds,
            failure_timestamps=updated,
            opened_at=opened,
        )

    def record_success(self) -> CircuitBreaker:
        """Reset the breaker to closed state.

        Returns:
            A new :class:`CircuitBreaker` with all failure history cleared.
        """
        if self.opened_at is not None:
            logger.info("circuit_breaker_reset", agent_role=self.agent_role)

        return CircuitBreaker(
            agent_role=self.agent_role,
            threshold=self.threshold,
            window_seconds=self.window_seconds,
            cooldown_seconds=self.cooldown_seconds,
        )
