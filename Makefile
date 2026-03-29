.DEFAULT_GOAL := help
.PHONY: help install dev lint format typecheck test test-unit test-integration security clean docker-up docker-down docs-serve docs-build

# ── Meta ──────────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ─────────────────────────────────────────────────────────────
install: ## Install all dependencies (prod + dev)
	uv sync --all-extras

dev: install ## Install + copy .env.example if .env missing
	@test -f .env || cp .env.example .env && echo "Created .env from .env.example"

# ── Quality ───────────────────────────────────────────────────────────
lint: ## Run ruff linter
	uv run ruff check src/ tests/

format: ## Auto-format code with ruff
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck: ## Run mypy type checker
	uv run mypy src/

# ── Testing ───────────────────────────────────────────────────────────
test: ## Run all tests with coverage
	uv run pytest

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -m unit --no-header

test-integration: ## Run integration tests only
	uv run pytest tests/integration/ -m integration --no-header

# ── Security ──────────────────────────────────────────────────────────
security: ## Run security checks (bandit + pip-audit)
	uv run bandit -r src/ -c pyproject.toml
	uv run pip-audit

# ── Docker ────────────────────────────────────────────────────────────
docker-up: ## Start dev services (postgres, redis, neo4j)
	docker compose up -d

docker-down: ## Stop dev services
	docker compose down

docker-build: ## Build Colette container image
	docker build -t colette:latest .

# ── Cleanup ───────────────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info .mypy_cache/ .ruff_cache/ .pytest_cache/ htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ── Documentation ────────────────────────────────────────────────────
docs-serve: ## Serve docs locally with hot reload
	uv run mkdocs serve

docs-build: ## Build static docs site to site/
	uv run mkdocs build --strict

# ── All checks (CI equivalent) ───────────────────────────────────────
check: lint typecheck test security ## Run all quality checks
