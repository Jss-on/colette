# Colette

A multi-agent AI system that autonomously performs end-to-end software development for web applications -- from natural language requirements through production deployment and monitoring.

## Overview

Colette orchestrates 25 specialized AI agents across a six-stage SDLC pipeline:

```
User Request -> Requirements -> Design -> Implementation -> Testing -> Deployment -> Monitoring
```

Each stage has a supervisor agent managing 2-7 specialist agents. Routine tasks execute autonomously; critical decisions (production deploys, DB migrations, security architecture) require human approval via a four-tier escalation model.

### Key Capabilities

- **Full SDLC coverage:** Requirements analysis, system design, code generation, testing, deployment, and monitoring
- **Typed handoffs:** All inter-stage communication uses versioned Pydantic schemas -- no free-text handoffs
- **LLM-agnostic:** Claude, GPT, and Gemini via OpenRouter gateway with automatic fallback chains
- **Human oversight:** Four-tier approval model (T0 always-interrupt through T3 auto-approve)
- **Observability:** OpenTelemetry tracing, structured logging, and per-agent token budget tracking
- **Web UI:** React-based dashboard with pipeline visualization, agent board, and approval queue
- **Cloud-agnostic:** Runs on AWS, GCP, Azure, or on-premises

## Architecture

```
+-------------------+
|  Project          |    Orchestration: LangGraph StateGraph DAG
|  Orchestrator     |    Models: Opus (planning) / Sonnet (execution) / Haiku (validation)
+--------+----------+
         |
   +-----+-----+-----+-----+-----+-----+
   |     |     |     |     |     |     |
  Req   Des   Imp   Tst   Dep   Mon    Six pipeline stages
  Sup   Sup   Sup   Sup   Sup   Sup    Each with supervisor + specialists
   3     4     8     4     3     3      Agents per stage (25 total)
```

**Memory layer:** Hot (LangGraph context) -> Warm (Mem0 + Graphiti/Neo4j + pgvector) -> Cold (S3 archive)

**Context management:** Per-agent token budgets (100k/60k/30k), RAG with hybrid retrieval (BM25 + dense vectors + Cohere rerank), context summarization at 80% utilization

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker and Docker Compose (for dev services)
- Node.js (for web UI)

### Setup

```bash
# Install dependencies
make install

# Create .env from template and install pre-commit hooks
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
make hooks        # install pre-commit hooks
```

### CLI

```bash
uv run colette serve                                        # start API server (port 8000)
uv run colette submit --name "my-app" --description "..."   # submit a project
uv run colette status <project-id> --follow                 # stream progress via SSE
uv run colette approve <gate-id>                            # approve a quality gate
uv run colette config show                                  # show current config
```

### Web UI

```bash
make web-install  # install web UI dependencies
make web-dev      # start dev server (Vite + React)
make web          # build for production
```

## Project Structure

```
src/colette/
  agents/           # Subagent framework, async task manager, middleware
  api/              # FastAPI app, REST routes, SSE streaming, WebSocket
  backends/         # Backend protocol, composite backend, state management
  db/               # SQLAlchemy models, repositories, session management
  gates/            # Quality gate enforcement (per-stage gate evaluators)
  human/            # Human-in-the-loop approval workflows
  llm/              # OpenRouter gateway, model registry, structured output, embeddings
  memory/           # Hot/warm/cold memory tiers, RAG (indexer/retriever/chunker), context budgets
  observability/    # OpenTelemetry tracing, metrics, callbacks
  orchestrator/     # LangGraph pipeline DAG, runner, state, event bus, circuit breaker
  schemas/          # Typed Pydantic handoff schemas between stages
  security/         # RBAC, audit logging, secret filtering, prompt injection defense
  services/         # Backlog manager and business logic services
  stages/           # Six active SDLC stages (+ planning, triage, retrospective for future phases)
  tools/            # MCP tool integration (filesystem, git, terminal, npm, linter)
web/                # React + Vite web dashboard (pipeline view, agent board, approvals)
tests/
  unit/             # Fast, no external dependencies
  integration/      # Requires services (DB, Redis)
  e2e/              # Full pipeline tests
docs/               # User-facing docs (guide, architecture, getting started)
  internal/         # Specifications (SRS, system architecture, implementation guide)
```

## Configuration

All settings are managed via environment variables with `COLETTE_` prefix (see [`.env.example`](.env.example)):

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_DEFAULT_PLANNING_MODEL` | Model for planning/architecture | `anthropic/claude-opus-4-6` |
| `COLETTE_DEFAULT_EXECUTION_MODEL` | Model for code generation | `anthropic/claude-sonnet-4-6` |
| `COLETTE_DEFAULT_VALIDATION_MODEL` | Model for validation/review | `anthropic/claude-haiku-4-5` |
| `COLETTE_DEFAULT_REASONING_MODEL` | Model for bug-fixing/iteration | `anthropic/claude-opus-4-6` |
| `COLETTE_OPENROUTER_API_KEY` | OpenRouter API key | |
| `COLETTE_DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://colette:colette@localhost:5432/colette` |
| `COLETTE_REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `COLETTE_NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `COLETTE_CHECKPOINT_BACKEND` | Pipeline checkpoint storage | `memory` (dev) / `postgres` (prod) |

See `src/colette/config.py` for the full settings schema.

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/guide.md) | How to use Colette -- pipeline stages, configuration, extending |
| [Getting Started](docs/getting-started.md) | Setup and first project walkthrough |
| [Architecture](docs/architecture.md) | Architecture overview |
| [Sequence Diagrams](docs/sequence_diagram.md) | Pipeline sequence diagrams |
| [Web UI Plan](docs/web-ui-plan.md) | Web dashboard specifications |
| [Release](docs/RELEASE.md) | Release and deployment information |
| [Software Requirements Specification](docs/internal/Colette_Software_Requirements_Specification.md) | 164 requirements, MoSCoW prioritized, IEEE 830 |
| [System Architecture](docs/internal/MultiAgent_SDLC_System_Architecture.md) | Agent catalog, handoff schemas, memory tiers, MCP integration |
| [Implementation Guide](docs/internal/Complete_Guide_to_Building_AI_Agent_Systems.md) | Patterns and guidance for building the agent system |
| [Requirements Traceability](docs/internal/requirements_traceability_matrix.md) | Requirement -> architecture -> test mapping |
| [Development Phase Plan](docs/internal/development_phase_plan.md) | 9-phase implementation roadmap |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, workflow, and coding standards.

## Security

See [SECURITY.md](SECURITY.md) for the security policy and vulnerability reporting process.

## License

[MIT](LICENSE)
