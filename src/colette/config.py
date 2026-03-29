"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global Colette settings.

    Values are read from environment variables (prefixed COLETTE_)
    or a .env file.
    """

    model_config = {"env_prefix": "COLETTE_", "env_file": ".env", "extra": "ignore"}

    # ── LLM ───────────────────────────────────────────────────────────
    litellm_base_url: str = "http://localhost:4000"
    default_planning_model: str = "claude-opus-4-6-20250610"
    default_execution_model: str = "claude-sonnet-4-6-20250514"

    # ── Database ──────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://colette:colette@localhost:5432/colette"
    redis_url: str = "redis://localhost:6379/0"

    # ── Neo4j (knowledge graph) ───────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "colette-dev"  # noqa: S105

    # ── Agent defaults ────────────────────────────────────────────────
    agent_max_iterations: int = 25
    agent_timeout_seconds: int = 600
    supervisor_context_budget: int = 100_000
    specialist_context_budget: int = 60_000
    validator_context_budget: int = 30_000

    # ── Observability ─────────────────────────────────────────────────
    otel_service_name: str = "colette"
    log_level: str = "INFO"
    log_format: str = "json"

    # ── Server ────────────────────────────────────────────────────────
    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8000
    debug: bool = False
