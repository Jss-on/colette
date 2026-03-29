# Changelog

All notable changes to Colette will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [Unreleased]

## [0.1.0] - 2026-03-29

### Added

#### Phase 1: Agent Framework
- Circuit breaker pattern for LLM call protection (closed/open/half-open states)
- 4-step error recovery escalation chain (retry, compact, supervisor, human)
- Agent factory wrapping LangGraph's `create_react_agent` with timeout and iteration limits
- MCP tool base class with prompt-injection sanitization, audit logging, and secret redaction
- Tool registry with per-agent access control lists
- Built-in tools: filesystem (read/write/search), git (status/clone/branch/commit/push), terminal (sandboxed shell)
- OpenTelemetry tracing integration with OTLP exporter
- LangChain callback handler for token counts, tool metrics, and timing
- Observability metrics data models

#### Phase 0: Foundation Layer
- Typed Pydantic handoff schemas with versioning and size enforcement (32K char limit)
- Common enums (Priority, ApprovalTier) and reusable sub-models
- Stage-specific schemas: requirements, design, implementation, testing, deployment
- Agent configuration schema with role enum and model assignment
- LiteLLM gateway factory with fallback chains and retry/timeout
- Model registry mapping agent tiers (planning/execution/validation) to LLM models
- Token estimation utilities with budget checking and compaction threshold logic

#### Project Scaffold
- Project scaffolding: `pyproject.toml`, `src/colette/` package structure
- Six-stage pipeline package layout (requirements, design, implementation, testing, deployment, monitoring)
- Cross-cutting packages: orchestrator, memory, tools, gates, human, schemas
- Application config via `pydantic-settings` with env var support
- CLI entry point (`colette` command via Click)
- Development tooling: ruff (lint/format), mypy (typecheck), pytest (test)
- Docker Compose for dev services: PostgreSQL 16 + pgvector, Redis 7, Neo4j 5
- Multi-stage Dockerfile with non-root user
- Makefile with common dev commands
- GitHub Actions CI pipeline (lint, typecheck, test, security)
- `.env.example` with all config variables documented
- Initial test suite with unit tests for all implemented modules
- Standard project docs: LICENSE (MIT), CONTRIBUTING.md, SECURITY.md
