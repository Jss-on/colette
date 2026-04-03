# Multi-stage Dockerfile for Colette (FR-DEP-001)
# Build: docker build -t colette .
# Run:   docker run -p 8000:8000 colette

# -- Stage 1: Build --------------------------------------------------------
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install project
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
RUN uv sync --frozen --no-dev

# -- Stage 2: Runtime ------------------------------------------------------
FROM python:3.13-slim AS runtime

# Non-root user (FR-DEP-001: non-root)
RUN groupadd --gid 1000 colette && \
    useradd --uid 1000 --gid colette --create-home colette

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

# Put venv on PATH; default to production environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COLETTE_ENVIRONMENT=production

USER colette

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"]

ENTRYPOINT ["colette", "serve", "--host", "0.0.0.0", "--port", "8000"]
