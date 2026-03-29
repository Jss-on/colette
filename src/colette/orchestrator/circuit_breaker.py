"""Circuit breaker for agent invocations (FR-ORC-018).

When an agent fails ``threshold`` times within ``window_seconds``,
the breaker opens and blocks further invocations until ``cooldown_seconds``
have elapsed.  All mutations return a **new** instance (immutable).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Blocking invocations
    HALF_OPEN = "half_open"    # Cooldown expired, allowing a probe


@dataclass(frozen=True)
class CircuitBreaker:
    """Immutable circuit breaker with rolling-window failure tracking."""

    agent_role: str
    threshold: int = 3
    window_seconds: int = 300
    cooldown_seconds: int = 120

    failure_timestamps: tuple[float, ...] = field(default_factory=tuple)
    opened_at: float | None = None

    # ── Derived state ───────────────────────────────────────────────

    @property
    def failure_count_in_window(self) -> int:
        """Count failures within the rolling window."""
        cutoff = time.monotonic() - self.window_seconds
        return sum(1 for ts in self.failure_timestamps if ts > cutoff)

    @property
    def state(self) -> CircuitState:
        if self.opened_at is not None:
            elapsed = time.monotonic() - self.opened_at
            if elapsed >= self.cooldown_seconds:
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN
        return CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    # ── Mutations (return new instance) ─────────────────────────────

    def record_failure(self) -> CircuitBreaker:
        """Record a failure and open the breaker if threshold is reached."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        # Prune old timestamps and add the new one
        recent = tuple(ts for ts in self.failure_timestamps if ts > cutoff)
        updated = (*recent, now)

        opened = self.opened_at
        if len(updated) >= self.threshold and opened is None:
            opened = now

        return CircuitBreaker(
            agent_role=self.agent_role,
            threshold=self.threshold,
            window_seconds=self.window_seconds,
            cooldown_seconds=self.cooldown_seconds,
            failure_timestamps=updated,
            opened_at=opened,
        )

    def record_success(self) -> CircuitBreaker:
        """Reset the breaker to closed state."""
        return CircuitBreaker(
            agent_role=self.agent_role,
            threshold=self.threshold,
            window_seconds=self.window_seconds,
            cooldown_seconds=self.cooldown_seconds,
        )
