# Getting Started

## Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** -- fast Python package manager
- **Docker** and **Docker Compose** -- for dev services

## Installation

```bash
# Clone the repository
git clone https://github.com/Jss-on/colette.git
cd colette

# Install all dependencies
make install

# Create .env from template
make dev

# Start dev services (PostgreSQL + pgvector, Redis, Neo4j)
make docker-up
```

## Verify Installation

```bash
# Run all quality checks
make check

# Or individually
make lint         # ruff check
make format       # ruff format + autofix
make typecheck    # mypy strict mode
make test         # pytest with 80% coverage gate
make security     # bandit + pip-audit
```

## CLI

```bash
uv run colette --version
uv run colette --help
uv run colette --log-level DEBUG --log-format console
```

## Configuration

All settings are managed via environment variables prefixed with `COLETTE_`.
See [`.env.example`](https://github.com/Jss-on/colette/blob/main/.env.example) for the full list.

Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_LLM_PLANNING_MODEL` | Model for planning/architecture | `claude-sonnet-4-20250514` |
| `COLETTE_LLM_EXECUTION_MODEL` | Model for code generation | `claude-sonnet-4-20250514` |
| `COLETTE_LLM_VALIDATION_MODEL` | Model for validation/review | `claude-haiku-4-5-20251001` |
| `COLETTE_DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `COLETTE_LOG_LEVEL` | Logging level | `INFO` |
| `COLETTE_LOG_FORMAT` | Log output format (`json` or `console`) | `json` |

See the full settings schema: [`colette.config.Settings`](api/config.md)

## Building Documentation

```bash
# Serve docs locally with hot reload
make docs-serve

# Build static site to site/
make docs-build
```
