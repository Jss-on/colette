"""Tests for error recovery escalation chain (FR-ORC-013)."""

from __future__ import annotations

import pytest

from colette.orchestrator.error_recovery import (
    ErrorRecoveryPolicy,
    EscalationLevel,
    EscalationResult,
    execute_with_recovery,
)


class TestEscalationResult:
    def test_create_success(self) -> None:
        r = EscalationResult(level=EscalationLevel.RETRY, success=True)
        assert r.success is True
        assert r.error is None

    def test_create_failure(self) -> None:
        r = EscalationResult(
            level=EscalationLevel.COMPACT, success=False, error="still failing"
        )
        assert r.success is False


class TestErrorRecoveryPolicy:
    def test_defaults(self) -> None:
        p = ErrorRecoveryPolicy()
        assert p.max_retries == 2
        assert p.enable_compaction is True
        assert p.enable_supervisor_escalation is True
        assert p.enable_human_escalation is True


class TestExecuteWithRecovery:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self) -> None:
        async def ok() -> str:
            return "done"

        result, log = await execute_with_recovery(ok)
        assert result == "done"
        assert len(log) == 0

    @pytest.mark.asyncio
    async def test_succeeds_on_retry(self) -> None:
        calls = {"count": 0}

        async def fails_once() -> str:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("transient")
            return "recovered"

        result, log = await execute_with_recovery(fails_once)
        assert result == "recovered"
        # Log contains the failure entry + success entry
        assert len(log) == 2
        assert log[0].level == EscalationLevel.RETRY
        assert log[0].success is False
        assert log[1].level == EscalationLevel.RETRY
        assert log[1].success is True

    @pytest.mark.asyncio
    async def test_exhausts_retries_then_compacts(self) -> None:
        calls = {"count": 0}

        async def fails_then_ok_on_compact() -> str:
            calls["count"] += 1
            if calls["count"] <= 3:  # 1 initial + 2 retries
                raise RuntimeError("still failing")
            return "compacted-ok"

        result, log = await execute_with_recovery(fails_then_ok_on_compact)
        assert result == "compacted-ok"
        # Should have RETRY failures then a COMPACT success
        retry_entries = [e for e in log if e.level == EscalationLevel.RETRY]
        compact_entries = [e for e in log if e.level == EscalationLevel.COMPACT]
        assert len(retry_entries) == 2
        assert all(not e.success for e in retry_entries)
        assert len(compact_entries) == 1
        assert compact_entries[0].success is True

    @pytest.mark.asyncio
    async def test_reaches_supervisor_level(self) -> None:
        calls = {"count": 0}

        async def fails_until_supervisor() -> str:
            calls["count"] += 1
            if calls["count"] <= 4:  # 1 initial + 2 retries + 1 compact
                raise RuntimeError("failing")
            return "supervisor-ok"

        result, log = await execute_with_recovery(fails_until_supervisor)
        assert result == "supervisor-ok"
        supervisor_entries = [e for e in log if e.level == EscalationLevel.SUPERVISOR]
        assert len(supervisor_entries) == 1
        assert supervisor_entries[0].success is True

    @pytest.mark.asyncio
    async def test_all_steps_fail_reaches_human(self) -> None:
        async def always_fails() -> str:
            raise RuntimeError("permanent failure")

        with pytest.raises(RuntimeError, match="permanent failure"):
            await execute_with_recovery(always_fails)

    @pytest.mark.asyncio
    async def test_disabled_steps_are_skipped(self) -> None:
        calls = {"count": 0}

        async def fails_then_ok() -> str:
            calls["count"] += 1
            if calls["count"] <= 1:  # Only the initial attempt fails
                raise RuntimeError("failing")
            return "ok"

        policy = ErrorRecoveryPolicy(
            max_retries=0, enable_compaction=False, enable_supervisor_escalation=True
        )
        result, log = await execute_with_recovery(fails_then_ok, policy=policy)
        assert result == "ok"
        # Should jump straight to supervisor (no retries, no compact)
        assert any(e.level == EscalationLevel.SUPERVISOR for e in log)
        assert not any(e.level == EscalationLevel.RETRY for e in log)
        assert not any(e.level == EscalationLevel.COMPACT for e in log)

    @pytest.mark.asyncio
    async def test_on_escalate_callback_called(self) -> None:
        escalations: list[EscalationResult] = []

        async def fails_once() -> str:
            if not escalations:
                raise RuntimeError("first fail")
            return "ok"

        async def on_esc(result: EscalationResult) -> None:
            escalations.append(result)

        result, log = await execute_with_recovery(fails_once, on_escalate=on_esc)
        assert result == "ok"
        assert len(escalations) >= 1
