# Colette

A multi-agent AI system that autonomously performs end-to-end software development for web applications -- from natural language requirements through production deployment and monitoring.

## Overview

Colette orchestrates 16 specialized AI agents across a six-stage SDLC pipeline:

```
User Request -> Requirements -> Design -> Implementation -> Testing -> Deployment -> Monitoring
```

Each stage has a supervisor agent managing 2-4 specialist agents. Routine tasks execute autonomously; critical decisions (production deploys, DB migrations, security architecture) require human approval.

### Key Capabilities

- **Full SDLC coverage:** Requirements analysis, system design, code generation, testing, deployment, and monitoring
- **Typed handoffs:** All inter-stage communication uses versioned Pydantic schemas -- no free-text handoffs
- **LLM-agnostic:** Claude, GPT, and Gemini via LiteLLM gateway with automatic fallback chains
- **Human oversight:** Four-tier approval model from fully autonomous to human-required
- **Observability:** OpenTelemetry tracing, structured logging, and per-agent token budget tracking
- **Cloud-agnostic:** Runs on AWS, GCP, Azure, or on-premises

## Architecture

```
+-------------------+
|  Project          |    Orchestration: LangGraph DAG
|  Orchestrator     |    Models: Opus (planning) / Sonnet (execution) / Haiku (validation)
+--------+----------+
         |
   +-----+-----+-----+-----+-----+-----+
   |     |     |     |     |     |     |
  Req   Des   Imp   Tst   Dep   Mon    Six pipeline stages
  Sup   Sup   Sup   Sup   Sup   Sup    Each with supervisor + specialists
```

**Memory layer:** Hot (LangGraph context) -> Warm (Mem0 + Graphiti + pgvector) -> Cold (S3 archive)

**Context management:** Per-agent token budgets, RAG with hybrid retrieval (BM25 + dense vectors + Cohere rerank), Morph Compact at 70% utilization

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker and Docker Compose (for dev services)

### Setup

```bash
# Install dependencies
make install

# Create .env from template and install
make dev

# Start dev services (PostgreSQL + pgvector, Redis, Neo4j)
make docker-up
```

### Development

```bash
# Run all quality checks (lint + typecheck + test + security)
make check

# Individual commands
make lint         # ruff check
make format       # ruff format + autofix
make typecheck    # mypy strict mode
make test         # pytest with 80% coverage gate
make test-unit    # unit tests only
make security     # bandit + pip-audit
```

### CLI

```bash
uv run colette --version
uv run colette --help
```

## Project Structure

```
src/colette/
  schemas/          # Typed Pydantic handoff schemas
  orchestrator/     # Agent factory, circuit breaker, error recovery
  llm/              # LiteLLM gateway, model registry, token counting
  tools/            # MCP tool integration (filesystem, git, terminal)
  observability/    # OpenTelemetry tracing, metrics, callbacks
  stages/           # Six SDLC pipeline stages
  memory/           # Hot/warm/cold memory tiers
  gates/            # Quality gate enforcement
  human/            # Human-in-the-loop approval
tests/
  unit/             # Fast, no external dependencies
  integration/      # Requires services (DB, Redis)
  e2e/              # Full pipeline tests
docs/               # Specifications and architecture documents
```

## Configuration

All settings are managed via environment variables (see [`.env.example`](.env.example)):

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_LLM_PLANNING_MODEL` | Model for planning/architecture | `claude-sonnet-4-20250514` |
| `COLETTE_LLM_EXECUTION_MODEL` | Model for code generation | `claude-sonnet-4-20250514` |
| `COLETTE_LLM_VALIDATION_MODEL` | Model for validation/review | `claude-haiku-4-5-20251001` |
| `COLETTE_DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `COLETTE_REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `COLETTE_NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |

See `src/colette/config.py` for the full settings schema.

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/guide.md) | How to use Colette -- pipeline stages, configuration, extending |
| [Software Requirements Specification](docs/Colette_Software_Requirements_Specification.md) | 164 requirements, MoSCoW prioritized, IEEE 830 |
| [System Architecture](docs/MultiAgent_SDLC_System_Architecture.md) | Agent catalog, handoff schemas, memory tiers, MCP integration |
| [Implementation Guide](docs/Complete_Guide_to_Building_AI_Agent_Systems.md) | Patterns and guidance for building the agent system |
| [Requirements Traceability](docs/requirements_traceability_matrix.md) | Requirement -> architecture -> test mapping |
| [Development Phase Plan](docs/development_phase_plan.md) | 9-phase implementation roadmap |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, workflow, and coding standards.

## Security

See [SECURITY.md](SECURITY.md) for the security policy and vulnerability reporting process.

## License

[MIT](LICENSE)
