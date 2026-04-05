# Contributing to Colette

Thank you for your interest in contributing to Colette. This guide covers the development setup, workflow, and standards expected for contributions.

## Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- **Docker** and **Docker Compose** for dev services (PostgreSQL, Redis, Neo4j)
- **Git**

## Getting Started

```bash
# Clone the repository
git clone https://github.com/Jss-on/colette.git
cd colette

# Install all dependencies + pre-commit hooks + .env
make dev

# Start dev services
make docker-up

# Verify everything works
make check
```

The `make dev` command automatically installs pre-commit hooks that enforce conventional commits and run ruff on every commit.

## Branch Strategy

We use **trunk-based development** with short-lived feature branches:

- **`main`** is the trunk — always releasable, protected by CI
- Feature branches are short-lived (< 1 week) and merge via pull request
- No `develop` branch, no long-lived release branches
- Releases are cut from `main` via git tags (see [Release Process](docs/RELEASE.md))

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feat/your-feature-name
```

Branch naming conventions:
- `feat/` for new features
- `fix/` for bug fixes
- `refactor/` for refactoring
- `docs/` for documentation changes
- `test/` for test additions/fixes
- `chore/` for maintenance tasks

### 2. Write Tests First (TDD)

We follow test-driven development:

1. Write a failing test in `tests/unit/`, `tests/integration/`, or `tests/e2e/`
2. Run the test to confirm it fails: `make test-unit`
3. Write the minimal implementation to pass
4. Refactor as needed
5. Verify coverage is at or above 80%

### 3. Run Quality Checks

Before committing, run the full check suite:

```bash
make check    # lint + typecheck + test + security
```

Or run individual checks:

```bash
make lint         # ruff check
make format       # ruff format + fix
make typecheck    # mypy strict mode
make test         # pytest with coverage
make security     # bandit + pip-audit
```

### 4. Commit

Use [conventional commits](https://www.conventionalcommits.org/):

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

Examples:
```
feat: add requirements analyst agent
fix: correct token budget overflow in supervisor
docs: update architecture diagram for memory layer
test: add integration tests for LLM gateway fallback
```

### 5. Open a Pull Request

- Keep PRs focused on a single concern
- Include a summary of changes and motivation
- Reference related issues
- Ensure all CI checks pass before requesting review

## Code Standards

### Style

- **Line length:** 99 characters
- **Formatter:** ruff format
- **Linter:** ruff check (pycodestyle, pyflakes, isort, bugbear, bandit, and more)
- **Type checker:** mypy in strict mode

### Patterns

- **Immutability:** Create new objects instead of mutating existing ones
- **File size:** Keep files under 800 lines; extract when they grow
- **Function size:** Keep functions under 50 lines
- **Error handling:** Handle errors explicitly at every level; never silently swallow them
- **Input validation:** Validate at system boundaries using Pydantic schemas

### Architecture

- All inter-stage communication uses **typed Pydantic handoff schemas** (see `src/colette/schemas/`)
- All LLM calls go through the **OpenRouter gateway** (`src/colette/llm/gateway.py`)
- All external tool access uses **MCP tools** with sanitization and audit logging (`src/colette/tools/`)
- Agents are created via the **agent factory** (`src/colette/orchestrator/agent_factory.py`)

## Project Structure

```
src/colette/          # Source package (src-layout)
  schemas/            # Typed Pydantic handoff schemas
  orchestrator/       # Agent creation, circuit breaker, error recovery
  llm/                # LLM gateway, model registry, token counting
  tools/              # MCP tool integration
  observability/      # OpenTelemetry tracing, metrics, callbacks
  stages/             # Six SDLC pipeline stages
  memory/             # Hot/warm/cold memory tiers
  gates/              # Quality gate enforcement
  human/              # Human-in-the-loop approval
tests/
  unit/               # Fast tests, no external dependencies
  integration/        # Tests requiring services (DB, Redis, etc.)
  e2e/                # Full pipeline tests
```

## Test Organization

- **Unit tests** mirror the source structure: `tests/unit/test_<module>.py`
- **Integration tests** go in `tests/integration/` and are marked with `@pytest.mark.integration`
- **E2E tests** go in `tests/e2e/` and are marked with `@pytest.mark.e2e`
- Shared fixtures live in `tests/conftest.py`

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests (structured templates provided)
- Include steps to reproduce for bugs
- Include expected vs actual behavior

## Releases

See [docs/RELEASE.md](docs/RELEASE.md) for the full release process. Quick summary:

```bash
make bump-patch   # or bump-minor / bump-major
make release      # pushes tag → triggers CI → GitHub Release + Docker image
git push origin main
```

## Security

If you discover a security vulnerability, please follow our [Security Policy](SECURITY.md) instead of opening a public issue.
