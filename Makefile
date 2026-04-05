.DEFAULT_GOAL := help
.PHONY: help install dev hooks lint format typecheck test test-unit test-integration security clean docker-up docker-down docs-serve docs-build changelog bump-patch bump-minor bump-major release web web-dev web-install

# ── Meta ──────────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ─────────────────────────────────────────────────────────────
install: ## Install all dependencies (prod + dev)
	uv sync --all-extras

dev: install hooks ## Install + copy .env.example + install hooks
	@test -f .env || cp .env.example .env && echo "Created .env from .env.example"

hooks: ## Install pre-commit hooks (conventional commits, ruff, etc.)
	uv run pre-commit install --hook-type commit-msg --hook-type pre-commit

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
	uv run pytest tests/unit/ --no-header

test-integration: ## Run integration tests only
	uv run pytest tests/integration/ -m integration --no-header

# ── Security ──────────────────────────────────────────────────────────
security: ## Run security checks (bandit + pip-audit)
	PYTHONUTF8=1 uv run bandit -r src/ -c pyproject.toml || true
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

# ── Release ──────────────────────────────────────────────────────────
CURRENT_VERSION = $(shell git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//')

changelog: ## Regenerate CHANGELOG.md from full git history
	git-cliff --output CHANGELOG.md

bump-patch: check ## Bump patch version (e.g. 0.1.0 → 0.1.1), tag, update changelog
	$(call bump,patch)

bump-minor: check ## Bump minor version (e.g. 0.1.0 → 0.2.0), tag, update changelog
	$(call bump,minor)

bump-major: check ## Bump major version (e.g. 0.1.0 → 1.0.0), tag, update changelog
	$(call bump,major)

release: ## Push latest tag to trigger GitHub release workflow
	@TAG=$$(git describe --tags --abbrev=0) && \
	echo "Pushing $$TAG to origin..." && \
	git push origin $$TAG && \
	echo "Release workflow triggered for $$TAG"

define bump
	@echo "Current version: $(CURRENT_VERSION)"
	@NEXT=$$(python -c " \
		parts = '$(CURRENT_VERSION)'.split('.'); \
		idx = {'major': 0, 'minor': 1, 'patch': 2}['$(1)']; \
		parts[idx] = str(int(parts[idx]) + 1); \
		parts[idx+1:] = ['0'] * (2 - idx); \
		print('.'.join(parts))"); \
	echo "Next version: $$NEXT"; \
	git-cliff --tag "v$$NEXT" --output CHANGELOG.md; \
	git add CHANGELOG.md; \
	git commit -m "chore(release): v$$NEXT"; \
	git tag -a "v$$NEXT" -m "v$$NEXT"; \
	echo "Tagged v$$NEXT — run 'make release' to push and trigger CI."
endef

# ── Web UI ───────────────────────────────────────────────────────────
web: ## Build web UI for production
	cd web && npm run build

web-dev: ## Start web UI dev server
	cd web && npm run dev

web-install: ## Install web UI dependencies
	cd web && npm install

# ── All checks (CI equivalent) ───────────────────────────────────────
check: lint typecheck test-unit security ## Run all quality checks
