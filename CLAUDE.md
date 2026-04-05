# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Colette** is a multi-agent AI system that autonomously performs end-to-end software development. It takes a natural language project description and runs it through a 6-stage SDLC pipeline (Requirements → Design → Implementation → Testing → Deployment → Monitoring), each with supervisor + specialist agents, quality gates between stages, and human-in-the-loop approval for critical decisions.

**Colette is a standalone CLI tool** (like Claude Code). Users run `uv run colette submit --name "app" --description "..."` and watch progress via SSE streaming. It is NOT a framework/library/SDK.

## Development Commands

```bash
# Setup
make install                  # uv sync --all-extras
make dev                      # install + create .env from .env.example

# Quality
make lint                     # ruff check src/ tests/
make format                   # ruff format + ruff check --fix
make typecheck                # mypy src/ (strict mode)
make check                    # lint + typecheck + test-unit + security

# Testing
make test                     # pytest with coverage (80% min, --cov-fail-under=80)
make test-unit                # pytest tests/unit/ only
make test-integration         # pytest tests/integration/ -m integration
uv run pytest tests/unit/stages/test_requirements_stage.py  # single file
uv run pytest tests/unit/ -k "test_gate"                    # by name pattern
uv run pytest tests/unit/ --no-cov                          # skip coverage

# Run
uv run colette serve          # start FastAPI server (uvicorn, port 8000)
uv run colette submit --name "my-app" --description "..."   # submit a project
uv run colette status <project-id> --follow                 # stream progress
uv run colette approve <gate-id>                            # approve a gate
uv run colette config show                                  # show current config

# Services (needed for integration tests / prod)
make docker-up                # postgres, redis, neo4j
make docker-down
```

## Architecture

### Pipeline Flow

The core is a LangGraph `StateGraph` in `orchestrator/pipeline.py`. Six stage nodes and six gate nodes form a linear DAG:

```
START → requirements → req_gate → design → design_gate → implementation → impl_gate
      → testing → test_gate → deployment → staging_gate → monitoring → END
```

Each stage node calls `stages/<name>/stage.py:run_stage(state)` which delegates to a supervisor (`supervisor.py`), which orchestrates 2-3 specialist agents. Each gate node calls `gates/<name>_gate.py:evaluate()` which checks handoff quality (completeness scores, required fields, thresholds).

### State Threading

`PipelineState` (in `orchestrator/state.py`) is a `TypedDict` threaded through all nodes. Key fields:
- `handoffs: dict[str, dict]` — each stage writes its output handoff here; the next stage reads from it
- `stage_statuses: dict[str, str]` — tracks PENDING/RUNNING/COMPLETED/FAILED per stage
- `progress_events`, `error_log` — append-only lists (using `operator.add` reducer for concurrency safety)
- `approval_requests`, `approval_decisions` — human-in-the-loop state

### How Agents Call LLMs

All agent LLM calls go through `llm/structured.py:invoke_structured()`:

```python
result = await invoke_structured(
    system_prompt=ANALYST_SYSTEM_PROMPT,
    user_content=f"Project Description:\n\n{user_request}",
    output_type=AnalysisResult,    # Pydantic model — response parsed into this
    settings=settings,
    model_tier=ModelTier.EXECUTION, # PLANNING / EXECUTION / VALIDATION
)
```

This function: augments the system prompt with the JSON schema of `output_type`, sends the request via `llm/gateway.py` (OpenRouter-backed, with fallback chains), extracts JSON from the response, and validates it into the Pydantic model. A `ColletteCallbackHandler` is auto-attached for event emission.

### LLM Gateway & Model Tiers

`llm/gateway.py:create_chat_model_for_tier()` maps `ModelTier` → model string via config:
- **PLANNING**: `default_planning_model` (Claude Sonnet 4.6)
- **EXECUTION**: `default_execution_model` (Claude Sonnet 4.6)
- **VALIDATION**: `default_validation_model` (Claude Haiku 4.5)

Each tier has optional fallback chains (`planning_fallback_models`, etc.) tried in order on failure. A `GuardedChatModel` wrapper blocks LLM calls for non-running projects (checked via `llm/registry.py:project_status_registry`).

### Handoff Schemas

Typed Pydantic models in `schemas/` define the contract between stages. Each is frozen/immutable:
- `RequirementsToDesignHandoff` — user stories, NFRs, constraints, completeness score
- `DesignToImplementationHandoff` — OpenAPI spec, DB entities, tech stack, ADRs
- `ImplementationToTestingHandoff` — generated files, packages, migrations
- `TestingToDeploymentHandoff` — test files, coverage metrics, security findings
- `DeploymentToMonitoringHandoff` — deployment configs, container image, infra manifest

Shared types (UserStory, NFRSpec, EntitySpec, etc.) live in `schemas/common.py`.

### Quality Gates

Each gate in `gates/` implements the `QualityGate` Protocol (async `evaluate(state) -> QualityGateResult`). Gates never raise exceptions — they always return a result with `passed: bool` and `reasons: list[str]`. The `GateRegistry` in `gates/base.py` provides lookup by name.

### Event Bus & SSE Streaming

`orchestrator/event_bus.py` provides an in-process pub/sub per project. Stage nodes and agent callbacks emit `PipelineEvent`s (STAGE_STARTED, AGENT_THINKING, GATE_PASSED, etc.). The API layer (`api/routes/pipelines.py`) streams these to clients as SSE. Context variables (`event_bus_var`, `project_id_var`, `stage_var`) propagate the bus through async call chains.

### Configuration

`config.py:Settings` uses `pydantic-settings` with `COLETTE_` env prefix. All settings load from env vars or `.env` file. Key groups: LLM models/fallbacks, database URLs, agent budgets (100k/60k/30k tokens), human-in-the-loop thresholds (0.60 escalation, 0.85 auto-approve), observability, security toggles.

## Key Directories

- `src/colette/stages/<name>/` — each has `stage.py` (entry), `supervisor.py` (orchestrates agents), specialist agents, `prompts.py`
- `src/colette/llm/` — gateway.py (OpenRouter + fallbacks), structured.py (typed output), registry.py (project status guard), embeddings.py (httpx-based)
- `src/colette/orchestrator/` — pipeline.py (LangGraph DAG), runner.py (execution manager), state.py, event_bus.py, circuit_breaker.py
- `src/colette/memory/` — manager.py (facade), project_memory.py (Mem0), knowledge_graph.py (Neo4j, null fallback), rag/ (indexer, retriever, evaluator, chunker), context/ (budget tracker, compactor)
- `src/colette/api/` — FastAPI app with routes for projects, pipelines (SSE), approvals, artifacts, WebSocket
- `src/colette/security/` — RBAC, audit logging, secret filtering, prompt injection defense, MCP tool pinning
- `src/colette/tools/` — MCP-wrapped tools (git, filesystem, terminal, npm, linter, etc.) extending `MCPBaseTool` with sanitization

## Testing Conventions

- Tests mirror `src/` under `tests/unit/` and `tests/integration/`
- `conftest.py` provides `settings` fixture (in-memory DB config), `mock_project_memory`, `mock_knowledge_graph`
- Markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`
- `asyncio_mode = "auto"` — async test functions just work
- Coverage enforced at 80% via `--cov-fail-under=80`

## Documentation

Planning docs live in `docs/`. Markdown versions are authoritative:
- `Colette_Software_Requirements_Specification.md` — 164 requirements (MoSCoW prioritized)
- `MultiAgent_SDLC_System_Architecture.md` — full architecture reference
- `Complete_Guide_to_Building_AI_Agent_Systems.md` — implementation guide
- `requirements_traceability_matrix.md` — requirement → component → test mapping
