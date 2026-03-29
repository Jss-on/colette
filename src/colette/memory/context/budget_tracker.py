"""Per-agent context budget enforcement (FR-MEM-004).

Immutable tracker — all mutations return a new instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from colette.memory.exceptions import BudgetExceededError

logger = structlog.get_logger(__name__)

# Slot names matching ContextBudgetAllocation fields
SLOT_NAMES = frozenset({
    "system_prompt",
    "tools",
    "retrieved_context",
    "history",
    "output",
})


@dataclass(frozen=True)
class ContextBudgetTracker:
    """Immutable per-agent context budget tracker.

    Tracks token usage per slot (system_prompt, tools, retrieved_context,
    history, output) against the total budget and per-slot allocations.
    All mutations return a new instance.
    """

    agent_role: str
    total_budget: int
    slot_allocations: tuple[tuple[str, float], ...] = field(
        default_factory=lambda: (
            ("system_prompt", 0.10),
            ("tools", 0.15),
            ("retrieved_context", 0.35),
            ("history", 0.15),
            ("output", 0.25),
        )
    )
    slot_usage: tuple[tuple[str, int], ...] = field(default_factory=tuple)

    @property
    def _allocations_dict(self) -> dict[str, float]:
        return dict(self.slot_allocations)

    @property
    def _usage_dict(self) -> dict[str, int]:
        return dict(self.slot_usage)

    def slot_budget(self, slot: str) -> int:
        """Maximum tokens allowed for the given slot."""
        alloc = self._allocations_dict.get(slot, 0.0)
        return int(self.total_budget * alloc)

    def slot_used(self, slot: str) -> int:
        """Tokens currently used in the given slot."""
        return self._usage_dict.get(slot, 0)

    def available_tokens(self, slot: str) -> int:
        """Remaining tokens for the given slot."""
        return max(0, self.slot_budget(slot) - self.slot_used(slot))

    @property
    def total_used(self) -> int:
        """Total tokens used across all slots."""
        return sum(v for _, v in self.slot_usage)

    @property
    def utilization(self) -> float:
        """Current utilization as a fraction (0.0 to 1.0+)."""
        if self.total_budget <= 0:
            return 0.0
        return self.total_used / self.total_budget

    def needs_compaction(self, threshold: float = 0.70) -> bool:
        """Whether utilization exceeds the compaction threshold."""
        return self.utilization >= threshold

    def record_usage(self, slot: str, tokens: int) -> ContextBudgetTracker:
        """Record token usage for a slot. Returns a new tracker.

        Raises BudgetExceededError if the slot limit is exceeded.
        """
        current = self.slot_used(slot)
        new_total = current + tokens
        limit = self.slot_budget(slot)

        if new_total > limit:
            raise BudgetExceededError(slot, new_total, limit)

        usage = dict(self.slot_usage)
        usage[slot] = new_total
        new_usage = tuple(sorted(usage.items()))

        logger.debug(
            "budget_usage_recorded",
            agent_role=self.agent_role,
            slot=slot,
            tokens=tokens,
            slot_used=new_total,
            slot_limit=limit,
        )
        return ContextBudgetTracker(
            agent_role=self.agent_role,
            total_budget=self.total_budget,
            slot_allocations=self.slot_allocations,
            slot_usage=new_usage,
        )

    def to_summary(self) -> dict[str, object]:
        """Snapshot for observability logging."""
        allocs = self._allocations_dict
        usage = self._usage_dict
        return {
            "agent_role": self.agent_role,
            "total_budget": self.total_budget,
            "total_used": self.total_used,
            "utilization": round(self.utilization, 3),
            "slots": {
                slot: {
                    "budget": int(self.total_budget * allocs.get(slot, 0)),
                    "used": usage.get(slot, 0),
                    "available": self.available_tokens(slot),
                }
                for slot in SLOT_NAMES
            },
        }
