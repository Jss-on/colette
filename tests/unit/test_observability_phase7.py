"""Tests for observability finalization modules (NFR-OBS-002..006).

Covers cost_tracker, alerts, rag_monitor, and dashboards — the Phase 7
additions to the observability layer.  The Phase 1 modules (tracing,
callbacks, metrics) are tested in ``test_observability.py``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from colette.observability.alerts import (
    DEFAULT_ALERT_RULES,
    Alert,
    AlertRule,
    AlertSeverity,
    check_regression,
    evaluate_rule,
)
from colette.observability.cost_tracker import (
    CostAlert,
    CostRecord,
    PipelineCostSummary,
    StageCostSummary,
    aggregate_pipeline_costs,
    aggregate_stage_costs,
    calculate_cost,
    check_cost_overrun,
)
from colette.observability.dashboards import (
    QualityDashboard,
    build_dashboard,
)
from colette.observability.metrics import AgentInvocationRecord, Outcome
from colette.observability.rag_monitor import (
    RAGMonitorSummary,
    RAGTriadAlert,
    RAGTriadScore,
    evaluate_rag_triad,
    summarize_rag_metrics,
)

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sonnet_record() -> AgentInvocationRecord:
    """Agent invocation using sonnet pricing."""
    return AgentInvocationRecord(
        agent_id="test-agent-1",
        agent_role="backend_dev",
        model="claude-sonnet-4-6-20250514",
        input_tokens=1000,
        output_tokens=500,
        tool_calls=(),
        duration_ms=1500.0,
        outcome=Outcome.SUCCESS,
    )


@pytest.fixture
def opus_record() -> AgentInvocationRecord:
    """Agent invocation using opus pricing."""
    return AgentInvocationRecord(
        agent_id="test-agent-2",
        agent_role="system_architect",
        model="claude-opus-4-6-20250610",
        input_tokens=2000,
        output_tokens=1000,
        tool_calls=(),
        duration_ms=3000.0,
        outcome=Outcome.SUCCESS,
    )


@pytest.fixture
def unknown_model_record() -> AgentInvocationRecord:
    """Agent invocation with a model not in the pricing table."""
    return AgentInvocationRecord(
        agent_id="test-agent-3",
        agent_role="frontend_dev",
        model="some-unknown-model-v99",
        input_tokens=500,
        output_tokens=250,
        tool_calls=(),
        duration_ms=800.0,
        outcome=Outcome.SUCCESS,
    )


@pytest.fixture
def good_rag_score() -> RAGTriadScore:
    """RAG score with faithfulness above the default threshold."""
    return RAGTriadScore(
        context_relevance=0.92,
        faithfulness=0.95,
        answer_relevance=0.88,
        query="What is the deployment strategy?",
        retrieved_count=5,
        timestamp="2026-03-30T10:00:00+00:00",
    )


@pytest.fixture
def bad_rag_score() -> RAGTriadScore:
    """RAG score with faithfulness below the default threshold."""
    return RAGTriadScore(
        context_relevance=0.80,
        faithfulness=0.60,
        answer_relevance=0.75,
        query="How does authentication work?",
        retrieved_count=3,
        timestamp="2026-03-30T10:05:00+00:00",
    )


# ── CostTracker ───────────────────────────────────────────────────────


class TestCalculateCost:
    """Tests for calculate_cost()."""

    def test_sonnet_pricing(self, sonnet_record: AgentInvocationRecord) -> None:
        result = calculate_cost(sonnet_record)

        assert isinstance(result, CostRecord)
        assert result.agent_id == "test-agent-1"
        assert result.model == "claude-sonnet-4-6-20250514"
        # $3/1M input -> 1000 tokens = $0.003
        assert result.input_cost == pytest.approx(0.003)
        # $15/1M output -> 500 tokens = $0.0075
        assert result.output_cost == pytest.approx(0.0075)
        assert result.total_cost == pytest.approx(0.0105)
        assert result.currency == "USD"

    def test_opus_pricing(self, opus_record: AgentInvocationRecord) -> None:
        result = calculate_cost(opus_record)

        # $15/1M input -> 2000 tokens = $0.03
        assert result.input_cost == pytest.approx(0.03)
        # $75/1M output -> 1000 tokens = $0.075
        assert result.output_cost == pytest.approx(0.075)
        assert result.total_cost == pytest.approx(0.105)

    def test_unknown_model_falls_back_to_sonnet(
        self, unknown_model_record: AgentInvocationRecord
    ) -> None:
        result = calculate_cost(unknown_model_record)

        # Falls back to sonnet pricing: $3/1M input, $15/1M output
        # 500 input tokens = $0.0015, 250 output tokens = $0.00375
        assert result.input_cost == pytest.approx(0.0015)
        assert result.output_cost == pytest.approx(0.00375)
        assert result.total_cost == pytest.approx(0.00525)
        # Model field preserves the original unknown model name
        assert result.model == "some-unknown-model-v99"

    def test_cost_record_is_frozen(self, sonnet_record: AgentInvocationRecord) -> None:
        result = calculate_cost(sonnet_record)

        with pytest.raises(ValidationError):
            result.total_cost = 999.0  # type: ignore[misc]

    def test_zero_tokens(self) -> None:
        record = AgentInvocationRecord(
            agent_id="zero",
            agent_role="test",
            model="claude-sonnet-4-6-20250514",
            input_tokens=0,
            output_tokens=0,
            tool_calls=(),
            duration_ms=0.0,
            outcome=Outcome.SUCCESS,
        )
        result = calculate_cost(record)

        assert result.total_cost == pytest.approx(0.0)


class TestAggregateStageCosts:
    """Tests for aggregate_stage_costs()."""

    def test_sums_correctly(
        self,
        sonnet_record: AgentInvocationRecord,
        opus_record: AgentInvocationRecord,
    ) -> None:
        result = aggregate_stage_costs("implementation", [sonnet_record, opus_record])

        assert isinstance(result, StageCostSummary)
        assert result.stage == "implementation"
        assert len(result.agent_costs) == 2
        # Sonnet: 0.0105, Opus: 0.105
        assert result.total_cost == pytest.approx(0.0105 + 0.105)
        # 1500 + 3000 total tokens
        assert result.token_count == 1500 + 3000

    def test_empty_records(self) -> None:
        result = aggregate_stage_costs("design", [])

        assert result.total_cost == pytest.approx(0.0)
        assert result.token_count == 0
        assert result.agent_costs == []

    def test_single_record(self, sonnet_record: AgentInvocationRecord) -> None:
        result = aggregate_stage_costs("testing", [sonnet_record])

        assert len(result.agent_costs) == 1
        assert result.total_cost == pytest.approx(0.0105)
        assert result.token_count == 1500


class TestAggregatePipelineCosts:
    """Tests for aggregate_pipeline_costs()."""

    def test_sums_across_stages(
        self,
        sonnet_record: AgentInvocationRecord,
        opus_record: AgentInvocationRecord,
    ) -> None:
        stage1 = aggregate_stage_costs("requirements", [sonnet_record])
        stage2 = aggregate_stage_costs("design", [opus_record])
        result = aggregate_pipeline_costs("proj-1", [stage1, stage2])

        assert isinstance(result, PipelineCostSummary)
        assert result.project_id == "proj-1"
        assert len(result.stage_summaries) == 2
        assert result.total_cost == pytest.approx(0.0105 + 0.105)
        assert result.total_tokens == 1500 + 3000

    def test_empty_stages(self) -> None:
        result = aggregate_pipeline_costs("proj-empty", [])

        assert result.total_cost == pytest.approx(0.0)
        assert result.total_tokens == 0
        assert result.stage_summaries == []


class TestCheckCostOverrun:
    """Tests for check_cost_overrun()."""

    def test_returns_none_when_under_threshold(self, sonnet_record: AgentInvocationRecord) -> None:
        cost = calculate_cost(sonnet_record)
        # Baseline 0.01, multiplier 2.0 => threshold 0.02
        # cost.total_cost ~= 0.0105 < 0.02
        result = check_cost_overrun(cost, baseline_cost=0.01, multiplier=2.0)

        assert result is None

    def test_returns_alert_when_over_threshold(self, sonnet_record: AgentInvocationRecord) -> None:
        cost = calculate_cost(sonnet_record)
        # Baseline 0.002, multiplier 2.0 => threshold 0.004
        # cost.total_cost ~= 0.0105 > 0.004
        result = check_cost_overrun(cost, baseline_cost=0.002, multiplier=2.0)

        assert result is not None
        assert isinstance(result, CostAlert)
        assert result.agent_id == "test-agent-1"
        assert result.current_cost == pytest.approx(0.0105)
        assert result.baseline_cost == pytest.approx(0.002)
        assert result.multiplier == pytest.approx(2.0)
        assert "exceeds" in result.message

    def test_returns_none_at_exact_threshold(self) -> None:
        cost_rec = CostRecord(
            agent_id="exact",
            agent_role="test",
            model="test",
            input_tokens=0,
            output_tokens=0,
            input_cost=0.0,
            output_cost=0.0,
            total_cost=0.10,
            currency="USD",
        )
        # Baseline 0.05, multiplier 2.0 => threshold 0.10; total_cost == 0.10
        result = check_cost_overrun(cost_rec, baseline_cost=0.05, multiplier=2.0)

        assert result is None

    def test_custom_multiplier(self, sonnet_record: AgentInvocationRecord) -> None:
        cost = calculate_cost(sonnet_record)
        # total_cost ~= 0.0105; baseline 0.001, multiplier 5.0 => threshold 0.005
        result = check_cost_overrun(cost, baseline_cost=0.001, multiplier=5.0)

        assert result is not None
        assert result.multiplier == pytest.approx(5.0)


# ── Alerts ────────────────────────────────────────────────────────────


class TestCheckRegression:
    """Tests for check_regression()."""

    def test_returns_none_when_within_threshold(self) -> None:
        # 5% drop (baseline 1.0, current 0.95) with 10% threshold -> no alert
        result = check_regression("success_rate", 0.95, 1.0, threshold_pct=10.0)

        assert result is None

    def test_returns_alert_when_drop_exceeds_threshold(self) -> None:
        # 20% drop (baseline 1.0, current 0.80) with 10% threshold -> alert
        result = check_regression("success_rate", 0.80, 1.0, threshold_pct=10.0)

        assert result is not None
        assert isinstance(result, Alert)
        assert result.severity == AlertSeverity.HIGH
        assert result.category == "regression"
        assert result.metric_name == "success_rate"
        assert "regressed" in result.message
        assert result.current_value == pytest.approx(0.80)

    def test_handles_zero_baseline(self) -> None:
        # Zero baseline should return None (avoid division by zero)
        result = check_regression("test_metric", 0.5, 0.0, threshold_pct=10.0)

        assert result is None

    def test_no_regression_when_improved(self) -> None:
        # Current is higher than baseline — no regression
        result = check_regression("throughput", 1.2, 1.0, threshold_pct=10.0)

        assert result is None

    def test_exact_threshold_boundary(self) -> None:
        # Exactly 10% drop with 10% threshold -> not triggered (must exceed)
        result = check_regression("metric", 0.90, 1.0, threshold_pct=10.0)

        assert result is None

    def test_alert_has_uuid_and_timestamp(self) -> None:
        result = check_regression("metric", 0.50, 1.0, threshold_pct=10.0)

        assert result is not None
        assert result.alert_id  # non-empty UUID string
        assert result.created_at  # non-empty ISO timestamp


class TestEvaluateRule:
    """Tests for evaluate_rule()."""

    def test_triggers_on_lt_condition(self) -> None:
        rule = AlertRule(
            name="low_rate",
            metric_name="success_rate",
            condition="lt",
            threshold=0.90,
            severity=AlertSeverity.HIGH,
        )
        result = evaluate_rule(rule, 0.85)

        assert result is not None
        assert isinstance(result, Alert)
        assert result.severity == AlertSeverity.HIGH
        assert result.category == "threshold"
        assert result.metric_name == "success_rate"

    def test_triggers_on_gt_condition(self) -> None:
        rule = AlertRule(
            name="high_cost",
            metric_name="cost_ratio",
            condition="gt",
            threshold=2.0,
            severity=AlertSeverity.MEDIUM,
        )
        result = evaluate_rule(rule, 2.5)

        assert result is not None
        assert result.severity == AlertSeverity.MEDIUM
        assert "triggered" in result.message

    def test_returns_none_when_not_triggered_lt(self) -> None:
        rule = AlertRule(
            name="low_rate",
            metric_name="success_rate",
            condition="lt",
            threshold=0.90,
            severity=AlertSeverity.HIGH,
        )
        # 0.95 is above the threshold, so "lt" should not trigger
        result = evaluate_rule(rule, 0.95)

        assert result is None

    def test_returns_none_when_not_triggered_gt(self) -> None:
        rule = AlertRule(
            name="high_cost",
            metric_name="cost_ratio",
            condition="gt",
            threshold=2.0,
            severity=AlertSeverity.HIGH,
        )
        # 1.5 is below the threshold, so "gt" should not trigger
        result = evaluate_rule(rule, 1.5)

        assert result is None

    def test_returns_none_at_exact_threshold_lt(self) -> None:
        rule = AlertRule(
            name="exact",
            metric_name="m",
            condition="lt",
            threshold=0.90,
            severity=AlertSeverity.LOW,
        )
        # Exactly at threshold — "lt" requires strictly less
        result = evaluate_rule(rule, 0.90)

        assert result is None

    def test_returns_none_at_exact_threshold_gt(self) -> None:
        rule = AlertRule(
            name="exact",
            metric_name="m",
            condition="gt",
            threshold=2.0,
            severity=AlertSeverity.LOW,
        )
        # Exactly at threshold — "gt" requires strictly greater
        result = evaluate_rule(rule, 2.0)

        assert result is None


class TestDefaultAlertRules:
    """Tests for DEFAULT_ALERT_RULES constant."""

    def test_is_tuple(self) -> None:
        assert isinstance(DEFAULT_ALERT_RULES, tuple)

    def test_contains_expected_rules(self) -> None:
        rule_names = {r.name for r in DEFAULT_ALERT_RULES}
        assert "low_agent_success_rate" in rule_names
        assert "low_pipeline_completion_rate" in rule_names
        assert "high_cost_overrun_ratio" in rule_names
        assert "high_escalation_rate" in rule_names

    def test_all_elements_are_alert_rules(self) -> None:
        for rule in DEFAULT_ALERT_RULES:
            assert isinstance(rule, AlertRule)

    def test_conditions_are_valid(self) -> None:
        for rule in DEFAULT_ALERT_RULES:
            assert rule.condition in {"gt", "lt"}

    def test_severities_are_valid(self) -> None:
        for rule in DEFAULT_ALERT_RULES:
            assert rule.severity in set(AlertSeverity)


# ── RAG Monitor ───────────────────────────────────────────────────────


class TestEvaluateRagTriad:
    """Tests for evaluate_rag_triad()."""

    def test_returns_none_when_faithfulness_above_threshold(
        self, good_rag_score: RAGTriadScore
    ) -> None:
        result = evaluate_rag_triad(good_rag_score, faithfulness_threshold=0.85)

        assert result is None

    def test_returns_alert_when_faithfulness_below_threshold(
        self, bad_rag_score: RAGTriadScore
    ) -> None:
        result = evaluate_rag_triad(bad_rag_score, faithfulness_threshold=0.85)

        assert result is not None
        assert isinstance(result, RAGTriadAlert)
        assert result.alert_type == "low_faithfulness"
        assert result.score == pytest.approx(0.60)
        assert result.threshold == pytest.approx(0.85)
        assert result.query == "How does authentication work?"
        assert "below threshold" in result.message

    def test_returns_none_at_exact_threshold(self) -> None:
        score = RAGTriadScore(
            context_relevance=0.90,
            faithfulness=0.85,
            answer_relevance=0.90,
            query="exact boundary test",
            retrieved_count=4,
            timestamp="2026-03-30T12:00:00+00:00",
        )
        result = evaluate_rag_triad(score, faithfulness_threshold=0.85)

        assert result is None

    def test_custom_threshold(self, good_rag_score: RAGTriadScore) -> None:
        # good_rag_score has faithfulness=0.95; with threshold 0.98 it should alert
        result = evaluate_rag_triad(good_rag_score, faithfulness_threshold=0.98)

        assert result is not None
        assert result.threshold == pytest.approx(0.98)

    def test_uses_default_threshold(self, bad_rag_score: RAGTriadScore) -> None:
        # Default threshold is 0.85; bad_rag_score has faithfulness=0.60
        result = evaluate_rag_triad(bad_rag_score)

        assert result is not None


class TestSummarizeRagMetrics:
    """Tests for summarize_rag_metrics()."""

    def test_computes_correct_averages(
        self,
        good_rag_score: RAGTriadScore,
        bad_rag_score: RAGTriadScore,
    ) -> None:
        result = summarize_rag_metrics(
            [good_rag_score, bad_rag_score], faithfulness_threshold=0.85
        )

        assert isinstance(result, RAGMonitorSummary)
        assert result.total_queries == 2
        assert result.avg_context_relevance == pytest.approx((0.92 + 0.80) / 2)
        assert result.avg_faithfulness == pytest.approx((0.95 + 0.60) / 2)
        assert result.avg_answer_relevance == pytest.approx((0.88 + 0.75) / 2)

    def test_counts_alerts_correctly(
        self,
        good_rag_score: RAGTriadScore,
        bad_rag_score: RAGTriadScore,
    ) -> None:
        result = summarize_rag_metrics(
            [good_rag_score, bad_rag_score], faithfulness_threshold=0.85
        )

        # Only bad_rag_score (faithfulness=0.60) triggers an alert
        assert result.alerts_triggered == 1

    def test_handles_empty_list(self) -> None:
        result = summarize_rag_metrics([], faithfulness_threshold=0.85)

        assert result.total_queries == 0
        assert result.avg_context_relevance == pytest.approx(0.0)
        assert result.avg_faithfulness == pytest.approx(0.0)
        assert result.avg_answer_relevance == pytest.approx(0.0)
        assert result.alerts_triggered == 0

    def test_all_good_scores(self, good_rag_score: RAGTriadScore) -> None:
        result = summarize_rag_metrics(
            [good_rag_score, good_rag_score], faithfulness_threshold=0.85
        )

        assert result.alerts_triggered == 0
        assert result.avg_faithfulness == pytest.approx(0.95)

    def test_all_bad_scores(self, bad_rag_score: RAGTriadScore) -> None:
        result = summarize_rag_metrics([bad_rag_score, bad_rag_score], faithfulness_threshold=0.85)

        assert result.alerts_triggered == 2


# ── Dashboards ────────────────────────────────────────────────────────


class TestBuildDashboard:
    """Tests for build_dashboard()."""

    def test_empty_records_returns_empty_metrics(self) -> None:
        result = build_dashboard("proj-empty", pipeline_records=[])

        assert isinstance(result, QualityDashboard)
        assert result.project_id == "proj-empty"
        assert len(result.metrics) == 7
        for series in result.metrics.values():
            assert series.points == []

    def test_all_seven_metric_keys_present(self) -> None:
        records = [
            {
                "stage": "requirements",
                "duration_ms": 1000.0,
                "outcome": "success",
                "cost": 0.01,
                "tokens": 500,
                "escalated": False,
                "hallucination_detected": False,
            },
        ]
        result = build_dashboard("proj-1", pipeline_records=records)

        expected_keys = {
            "pipeline_completion_rate",
            "stage_latency_p50",
            "stage_latency_p99",
            "agent_success_rate",
            "escalation_frequency",
            "cost_trend",
            "hallucination_rate",
        }
        assert set(result.metrics.keys()) == expected_keys

    def test_completion_rate(self) -> None:
        records = [
            {
                "stage": "impl",
                "duration_ms": 100.0,
                "outcome": "success",
                "cost": 0.01,
                "tokens": 100,
                "escalated": False,
                "hallucination_detected": False,
            },
            {
                "stage": "impl",
                "duration_ms": 200.0,
                "outcome": "failure",
                "cost": 0.02,
                "tokens": 200,
                "escalated": False,
                "hallucination_detected": False,
            },
        ]
        result = build_dashboard("proj-rate", pipeline_records=records)

        completion = result.metrics["pipeline_completion_rate"]
        assert len(completion.points) == 1
        assert completion.points[0].value == pytest.approx(0.5)

    def test_latency_computation(self) -> None:
        records = [
            {
                "stage": "test",
                "duration_ms": 100.0,
                "outcome": "success",
                "cost": 0.0,
                "tokens": 0,
                "escalated": False,
                "hallucination_detected": False,
            },
            {
                "stage": "test",
                "duration_ms": 200.0,
                "outcome": "success",
                "cost": 0.0,
                "tokens": 0,
                "escalated": False,
                "hallucination_detected": False,
            },
            {
                "stage": "test",
                "duration_ms": 300.0,
                "outcome": "success",
                "cost": 0.0,
                "tokens": 0,
                "escalated": False,
                "hallucination_detected": False,
            },
        ]
        result = build_dashboard("proj-lat", pipeline_records=records)

        p50 = result.metrics["stage_latency_p50"]
        assert len(p50.points) == 1
        assert p50.points[0].value == pytest.approx(200.0)

        p99 = result.metrics["stage_latency_p99"]
        assert len(p99.points) == 1
        assert p99.points[0].value > 200.0

    def test_escalation_frequency(self) -> None:
        records = [
            {
                "stage": "deploy",
                "duration_ms": 100.0,
                "outcome": "success",
                "cost": 0.0,
                "tokens": 0,
                "escalated": True,
                "hallucination_detected": False,
            },
            {
                "stage": "deploy",
                "duration_ms": 100.0,
                "outcome": "success",
                "cost": 0.0,
                "tokens": 0,
                "escalated": False,
                "hallucination_detected": False,
            },
            {
                "stage": "deploy",
                "duration_ms": 100.0,
                "outcome": "success",
                "cost": 0.0,
                "tokens": 0,
                "escalated": True,
                "hallucination_detected": False,
            },
        ]
        result = build_dashboard("proj-esc", pipeline_records=records)

        esc = result.metrics["escalation_frequency"]
        assert esc.points[0].value == pytest.approx(2.0 / 3.0)

    def test_hallucination_rate(self) -> None:
        records = [
            {
                "stage": "impl",
                "duration_ms": 100.0,
                "outcome": "success",
                "cost": 0.0,
                "tokens": 0,
                "escalated": False,
                "hallucination_detected": True,
            },
            {
                "stage": "impl",
                "duration_ms": 100.0,
                "outcome": "success",
                "cost": 0.0,
                "tokens": 0,
                "escalated": False,
                "hallucination_detected": False,
            },
        ]
        result = build_dashboard("proj-hall", pipeline_records=records)

        hall = result.metrics["hallucination_rate"]
        assert hall.points[0].value == pytest.approx(0.5)

    def test_cost_trend_has_per_record_points(self) -> None:
        records = [
            {
                "stage": "s1",
                "duration_ms": 100.0,
                "outcome": "success",
                "cost": 0.05,
                "tokens": 100,
                "escalated": False,
                "hallucination_detected": False,
                "timestamp": "2026-03-30T01:00:00+00:00",
            },
            {
                "stage": "s2",
                "duration_ms": 200.0,
                "outcome": "success",
                "cost": 0.10,
                "tokens": 200,
                "escalated": False,
                "hallucination_detected": False,
                "timestamp": "2026-03-30T02:00:00+00:00",
            },
        ]
        result = build_dashboard("proj-cost", pipeline_records=records)

        cost_series = result.metrics["cost_trend"]
        assert len(cost_series.points) == 2
        assert cost_series.points[0].value == pytest.approx(0.05)
        assert cost_series.points[1].value == pytest.approx(0.10)

    def test_dashboard_is_frozen(self) -> None:
        result = build_dashboard("proj-frozen", pipeline_records=[])

        with pytest.raises(ValidationError):
            result.project_id = "changed"  # type: ignore[misc]

    def test_generated_at_is_populated(self) -> None:
        result = build_dashboard("proj-ts", pipeline_records=[])

        assert result.generated_at  # non-empty ISO timestamp string

    def test_metric_units(self) -> None:
        records = [
            {
                "stage": "s",
                "duration_ms": 100.0,
                "outcome": "success",
                "cost": 0.01,
                "tokens": 50,
                "escalated": False,
                "hallucination_detected": False,
            },
        ]
        result = build_dashboard("proj-units", pipeline_records=records)

        assert result.metrics["pipeline_completion_rate"].unit == "ratio"
        assert result.metrics["stage_latency_p50"].unit == "ms"
        assert result.metrics["stage_latency_p99"].unit == "ms"
        assert result.metrics["agent_success_rate"].unit == "ratio"
        assert result.metrics["escalation_frequency"].unit == "ratio"
        assert result.metrics["cost_trend"].unit == "USD"
        assert result.metrics["hallucination_rate"].unit == "ratio"
