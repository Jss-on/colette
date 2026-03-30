"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global Colette settings.

    Values are read from environment variables (prefixed COLETTE_)
    or a .env file.
    """

    model_config = {"env_prefix": "COLETTE_", "env_file": ".env", "extra": "ignore"}

    # ── LLM — primary models ────────────────────────────────────────
    litellm_base_url: str = "http://localhost:4000"
    default_planning_model: str = "claude-opus-4-6-20250610"
    default_execution_model: str = "claude-sonnet-4-6-20250514"
    default_validation_model: str = "claude-haiku-4-5-20251001"

    # ── LLM — fallback chains (FR-ORC-014) ──────────────────────────
    planning_fallback_models: list[str] = Field(
        default=["gpt-5.4", "gemini-2.5-pro"],
        description="Fallback chain for planning tier: tried in order on failure.",
    )
    execution_fallback_models: list[str] = Field(
        default=["gpt-5.4-mini", "gemini-2.5-flash"],
        description="Fallback chain for execution tier.",
    )
    validation_fallback_models: list[str] = Field(
        default=["gpt-5.4-mini", "gemini-2.5-flash"],
        description="Fallback chain for validation tier.",
    )

    # ── LLM — embeddings & reranking ─────────────────────────────────
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1536
    reranker_model: str = "rerank-v3.5"

    # ── LLM — cost & caching ────────────────────────────────────────
    prompt_caching_enabled: bool = True
    llm_timeout_seconds: int = 120
    llm_max_retries: int = 2

    # ── Database ──────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://colette:colette@localhost:5432/colette"
    redis_url: str = "redis://localhost:6379/0"

    # ── Neo4j (knowledge graph) ───────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "colette-dev"  # noqa: S105

    # ── Agent defaults (FR-ORC-011/012, FR-MEM-004) ──────────────────
    agent_max_iterations: int = 25
    agent_timeout_seconds: int = 600
    supervisor_context_budget: int = 100_000
    specialist_context_budget: int = 60_000
    validator_context_budget: int = 30_000

    # ── Handoff (FR-ORC-024) ─────────────────────────────────────────
    handoff_max_chars: int = 32_000

    # ── Memory (FR-MEM-004/005/007/012) ─────────────────────────────
    compaction_threshold: float = 0.70
    rag_chunk_size: int = 512
    rag_faithfulness_threshold: float = 0.85
    knowledge_graph_enabled: bool = True
    cohere_api_key: str = ""
    cold_storage_endpoint: str = ""
    cold_storage_bucket: str = "colette-cold"
    memory_decay_enabled: bool = False

    # ── Pipeline (FR-ORC-003/006/007) ──────────────────────────────────
    checkpoint_backend: str = Field(
        default="memory",
        description="Checkpoint storage: 'memory' (dev) or 'postgres' (prod).",
    )
    checkpoint_db_url: str = ""
    max_concurrent_pipelines: int = 5
    progress_stream_interval_seconds: float = 1.0

    # ── Human-in-the-loop (FR-HIL-001/002/005/006) ──────────────────
    hil_confidence_threshold: float = Field(
        default=0.60,
        description="Confidence below this triggers escalation.",
    )
    hil_confidence_flag_threshold: float = Field(
        default=0.85,
        description="Confidence below this flags for review (above auto-approves).",
    )
    hil_t0_sla_seconds: int = 3600
    hil_t1_sla_seconds: int = 14400
    notification_channels: list[str] = Field(default_factory=lambda: ["in_app"])
    notification_slack_webhook: str = ""
    notification_email_from: str = ""

    # ── Observability ─────────────────────────────────────────────────
    otel_service_name: str = "colette"
    otel_exporter_endpoint: str = "http://localhost:4318"
    log_level: str = "INFO"
    log_format: str = "json"

    # ── Cost tracking (NFR-OBS-002/003) ──────────────────────────────
    cost_overrun_multiplier: float = Field(
        default=2.0,
        description="Alert when agent cost exceeds baseline x this multiplier.",
    )
    cost_currency: str = "USD"

    # ── Security — RBAC (NFR-SEC-008) ────────────────────────────────
    rbac_enabled: bool = True
    rbac_default_role: str = "observer"

    # ── Security — Audit (NFR-SEC-005) ───────────────────────────────
    audit_log_path: str = "logs/audit.jsonl"
    audit_retention_days: int = 365

    # ── Security — Secret filtering (NFR-SEC-002) ────────────────────
    secret_filter_enabled: bool = True

    # ── Security — MCP pinning (NFR-SEC-004/009) ─────────────────────
    mcp_pin_file: str = "mcp-pins.json"
    mcp_allow_unverified: bool = False

    # ── Security — Prompt injection (NFR-SEC-001) ────────────────────
    prompt_injection_defense_enabled: bool = True

    # ── Security — Memory guard (NFR-SEC-010) ────────────────────────
    memory_write_confidence_threshold: float = Field(
        default=0.70,
        description="Minimum confidence for autonomous memory writes.",
    )
    memory_high_importance_audit: bool = True

    # ── Observability — Alerts (NFR-OBS-005) ─────────────────────────
    regression_window_days: int = 7
    regression_threshold_pct: float = 10.0

    # ── Server ────────────────────────────────────────────────────────
    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8000
    debug: bool = False
