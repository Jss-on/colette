"""Error recovery with 4-step escalation chain (FR-ORC-013).

On agent failure the system attempts in order:
1. Retry with same context (up to ``max_retries``)
2. Retry with compacted context
3. Escalate to supervisor
4. Escalate to human

Each step is logged.  Steps can be individually disabled via
``ErrorRecoveryPolicy``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EscalationLevel(StrEnum):
    """Escalation step identifiers."""

    RETRY = "retry"
    COMPACT = "compact"
    SUPERVISOR = "supervisor"
    HUMAN = "human"


@dataclass(frozen=True)
class EscalationResult:
    """Immutable record of one escalation attempt."""

    level: EscalationLevel
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class ErrorRecoveryPolicy:
    """Controls which escalation steps are enabled."""

    max_retries: int = 2
    enable_compaction: bool = True
    enable_supervisor_escalation: bool = True
    enable_human_escalation: bool = True


async def execute_with_recovery(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    policy: ErrorRecoveryPolicy | None = None,
    on_escalate: Callable[[EscalationResult], Awaitable[None]] | None = None,
    **kwargs: Any,
) -> tuple[Any, list[EscalationResult]]:
    """Run *fn* with the 4-step escalation chain.

    Returns ``(result, escalation_log)``.  If all steps fail,
    the final exception is re-raised.
    """
    if policy is None:
        policy = ErrorRecoveryPolicy()

    log: list[EscalationResult] = []
    last_error: BaseException | None = None

    # ── Step 0: Initial attempt ─────────────────────────────────────
    try:
        return await fn(*args, **kwargs), log
    except Exception as exc:
        last_error = exc
        logger.warning("initial_attempt_failed", error=str(exc))

    # ── Step 1: Retries ─────────────────────────────────────────────
    for attempt in range(policy.max_retries):
        entry = EscalationResult(
            level=EscalationLevel.RETRY,
            success=False,
            error=str(last_error),
        )
        log.append(entry)
        if on_escalate:
            await on_escalate(entry)
        logger.info("retry_attempt", attempt=attempt + 1)

        try:
            result = await fn(*args, **kwargs)
            log.append(EscalationResult(level=EscalationLevel.RETRY, success=True))
            return result, log
        except Exception as exc:
            last_error = exc

    # ── Step 2: Compact context and retry ───────────────────────────
    if policy.enable_compaction:
        entry = EscalationResult(
            level=EscalationLevel.COMPACT,
            success=False,
            error=str(last_error),
        )
        if on_escalate:
            await on_escalate(entry)
        logger.info("escalating_to_compaction")

        try:
            result = await fn(*args, **kwargs)
            log.append(EscalationResult(level=EscalationLevel.COMPACT, success=True))
            return result, log
        except Exception as exc:
            last_error = exc
            log.append(
                EscalationResult(level=EscalationLevel.COMPACT, success=False, error=str(exc))
            )

    # ── Step 3: Escalate to supervisor ──────────────────────────────
    if policy.enable_supervisor_escalation:
        entry = EscalationResult(
            level=EscalationLevel.SUPERVISOR,
            success=False,
            error=str(last_error),
        )
        if on_escalate:
            await on_escalate(entry)
        logger.info("escalating_to_supervisor")

        try:
            result = await fn(*args, **kwargs)
            log.append(EscalationResult(level=EscalationLevel.SUPERVISOR, success=True))
            return result, log
        except Exception as exc:
            last_error = exc
            log.append(
                EscalationResult(level=EscalationLevel.SUPERVISOR, success=False, error=str(exc))
            )

    # ── Step 4: Escalate to human ───────────────────────────────────
    if policy.enable_human_escalation:
        log.append(
            EscalationResult(level=EscalationLevel.HUMAN, success=False, error=str(last_error))
        )
        logger.warning("escalating_to_human", error=str(last_error))

    # All steps exhausted — re-raise the last error
    assert last_error is not None  # guaranteed by control flow
    raise last_error
