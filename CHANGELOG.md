# Changelog

All notable changes to Colette will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [Unreleased]

## [0.1.0] - 2026-03-29

### Added
- Project scaffolding: `pyproject.toml`, `src/colette/` package structure
- Six-stage pipeline package layout (requirements, design, implementation, testing, deployment, monitoring)
- Cross-cutting packages: orchestrator, memory, tools, gates, human, schemas
- Base handoff schema (`HandoffSchema`) with versioning per FR-ORC-020/021
- Application config via `pydantic-settings` with env var support
- CLI entry point (`colette` command via Click)
- Development tooling: ruff (lint/format), mypy (typecheck), pytest (test)
- Docker Compose for dev services: PostgreSQL 16 + pgvector, Redis 7, Neo4j 5
- Multi-stage Dockerfile with non-root user
- Makefile with common dev commands
- GitHub Actions CI pipeline (lint, typecheck, test, security)
- `.env.example` with all config variables documented
- Initial test suite: version, config, schema smoke tests
