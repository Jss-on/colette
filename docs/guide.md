# Colette User Guide

Colette is a multi-agent AI system that turns a natural language description into a fully built web application -- from requirements through deployment. You interact with it via a CLI (like Claude Code) or REST API.

## Table of Contents

- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
  - [Agent Activity Display](#agent-activity-display)
- [API Reference](#api-reference)
- [Programmatic Usage (Python)](#programmatic-usage-python)
- [Configuration Reference](#configuration-reference)
- [Pipeline Stages](#pipeline-stages)
- [Human Oversight](#human-oversight)
- [Quality Gates](#quality-gates)
- [Extending Colette](#extending-colette)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Current Status](#current-status)

---

## How It Works

You provide a description of the app you want. Colette runs it through a six-stage pipeline, each managed by a supervisor agent with specialist agents:

```
Your Request
    |
    v
1. Requirements --- Analyst + Domain Researcher
    |                Produces: PRD, user stories, NFRs
    v
2. Design --------- System Architect + API Designer + UI/UX Designer
    |                Produces: architecture, OpenAPI spec, DB schema, UI components
    v
3. Implementation -- Frontend Dev + Backend Dev + DB Engineer
    |                Produces: React/Next.js code, API routes, migrations, seed data
    v
4. Testing -------- Unit Tester + Integration Tester + Security Scanner
    |                Produces: test suites, coverage report, security findings
    v
5. Deployment ----- CI/CD Engineer + Infrastructure Engineer
    |                Produces: GitHub Actions, Dockerfiles, K8s manifests
    v
6. Monitoring ----- Observability Agent + Incident Response
                     Produces: dashboards, alerts, SLO tracking
```

Each stage passes its output to the next via a **typed handoff schema** -- structured Pydantic models, not free text. Quality gates between stages enforce minimum standards (coverage thresholds, no critical security findings, etc.).

---

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.13+ | Runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Package manager |
| Docker + Docker Compose | latest | Dev services (PostgreSQL, Redis, Neo4j) |
| LLM API key | -- | At least one: Anthropic, OpenAI, or Google |

---

## Installation

### 1. Clone and install

```bash
git clone https://github.com/Jss-on/colette.git
cd colette

# Install all dependencies (prod + dev)
make install

# Or equivalently:
uv sync --all-extras
```

### 2. Create environment file

```bash
make dev
# This copies .env.example to .env if .env doesn't exist
```

### 3. Configure API keys

Edit `.env` and add at least one LLM provider key:

```bash
# Required: at least one provider
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

### 4. Start backing services

Colette uses PostgreSQL (with pgvector), Redis, and Neo4j:

```bash
make docker-up
# This runs: docker compose up -d
```

Services started:

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL (pgvector) | 5432 | Project data, pipeline state, vector search |
| Redis | 6379 | Caching, rate limiting |
| Neo4j | 7474 (HTTP), 7687 (Bolt) | Knowledge graph |

### 5. Verify installation

```bash
# Check CLI is installed
uv run colette --version

# Run all quality checks
make check
```

---

## Quick Start

### Example: Build a Todo App

**Step 1 -- Start the API server**

```bash
uv run colette serve
# Server starts at http://localhost:8000
# API docs at http://localhost:8000/api/v1/docs
```

**Step 2 -- Submit a project via CLI**

Open a new terminal:

```bash
uv run colette submit \
  --name "my-todo-app" \
  --description "Build a todo list web app with user registration and login (email + password), CRUD todos, mark as complete, filter by status (all/active/completed), PostgreSQL database, REST API with OpenAPI docs"
```

Or use interactive mode (type description, then press Ctrl+D / Ctrl+Z to submit):

```bash
uv run colette submit --name "my-todo-app"
# Type your description...
# Press Ctrl+D (Unix) or Ctrl+Z (Windows) to submit
```

**Step 3 -- Monitor progress**

```bash
# One-shot status check
uv run colette status <project-id>

# Stream real-time progress (SSE)
uv run colette status <project-id> --follow
```

**Step 4 -- Handle approvals**

When the pipeline hits a quality gate, it pauses and launches an interactive TUI where you can review the deliverables before deciding:

```
╭─── Review Required ──────────────────────────────────────────────────────╮
│ Stage:  Design                                                           │
│ Score:  1.00                                                             │
│                                                                          │
│   API Endpoints:     13                                                  │
│   DB Entities:       3                                                   │
│   UI Components:     40                                                  │
│                                                                          │
│  [1] API Endpoints (13)                                                  │
│  [2] DB Entities (3)                                                     │
│  [3] Source Files (24)                                                   │
│                                                                          │
│  [A] Approve   [R] Reject                                                │
╰──────────────────────────────────────────────────────────────────────────╯
```

The TUI (powered by Textual) lets you browse API endpoints, DB entities, UI components, source code files with syntax highlighting, and architecture decisions before approving or rejecting. Press `A` to approve, `R` to reject, or `Q` to quit.

You can also approve/reject via separate commands:

```bash
# Approve
uv run colette approve <approval-id> --comment "LGTM"

# Or reject
uv run colette reject <approval-id> --reason "Needs security review"
```

**Step 5 -- Download artifacts**

```bash
uv run colette download <project-id>
# Extracts generated files to colette-<id>/

# Or specify output directory
uv run colette download <project-id> --output ./my-todo-app
```

**Step 6 -- View logs**

```bash
# All logs
uv run colette logs <project-id>

# Filter by stage
uv run colette logs <project-id> --stage testing
```

---

## CLI Reference

```
colette [OPTIONS] COMMAND [ARGS]
```

### Global Options

| Option | Default | Description |
|--------|---------|-------------|
| `--version` | -- | Show version and exit |
| `--log-level` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `--log-format` | `json` | Log format: `json` or `console` |
| `--api-url` | `http://localhost:8000` | API server URL (env: `COLETTE_API_URL`) |

### Commands

#### `colette submit`

Submit a new project for autonomous development.

```bash
colette submit [--name NAME] [--description DESCRIPTION] [--activity MODE]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-n, --name` | `Untitled` | Project name |
| `-d, --description` | *(interactive)* | Project description in natural language |
| `--activity` | `status` | Agent activity display mode (see [Agent Activity Display](#agent-activity-display)) |

If `--description` is omitted, enters interactive mode where you type the description and press Ctrl+D/Ctrl+Z to submit.

After submission, Colette automatically streams live progress inline -- no need for a second terminal. Press Ctrl+C to detach (the pipeline continues running; use `colette status <id> --follow` to reattach).

#### `colette status`

Check pipeline status for a project.

```bash
colette status PROJECT_ID [--follow] [--activity MODE]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-f, --follow` | -- | Stream real-time progress events via SSE |
| `--activity` | `status` | Agent activity display mode (with `--follow`, see [Agent Activity Display](#agent-activity-display)) |

#### `colette approve`

Approve a pending gate request.

```bash
colette approve APPROVAL_ID [--comment COMMENT]
```

#### `colette reject`

Reject a pending gate request.

```bash
colette reject APPROVAL_ID [--reason REASON]
```

#### `colette resume`

Resume an interrupted project (re-enables LLM calls).

```bash
colette resume PROJECT_ID
```

When a server restarts, running pipelines are marked as "interrupted" and LLM calls are blocked. Use `resume` to reactivate a project and restart from the last completed stage.

#### `colette cancel`

Cancel a project permanently (blocks LLM calls, cannot be resumed).

```bash
colette cancel PROJECT_ID
```

#### `colette download`

Download generated artifacts for a project.

```bash
colette download PROJECT_ID [--output DIR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | `colette-<id>` | Output directory |

#### `colette logs`

View pipeline logs and progress events.

```bash
colette logs PROJECT_ID [--stage STAGE]
```

| Option | Description |
|--------|-------------|
| `-s, --stage` | Filter by stage name (requirements, design, implementation, testing, deployment, monitoring) |

#### `colette config show`

Display current configuration with secrets redacted.

```bash
colette config show
```

#### `colette config validate`

Validate that all required settings are present.

```bash
colette config validate
```

#### `colette serve`

Start the Colette API server.

```bash
colette serve [--host HOST] [--port PORT] [--workers N]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `0.0.0.0` | Bind host |
| `--port` | `8000` | Bind port |
| `--workers` | `1` | Number of uvicorn workers |

### Agent Activity Display

The `--activity` flag controls how much agent detail is shown during live progress streaming (`colette submit` and `colette status --follow`).

| Mode | Shows | Use case |
|------|-------|----------|
| `minimal` | Stage progress only (checkmarks, spinners) | CI/scripting |
| `status` (default) | Stage progress + active agent panel | Normal use |
| `conversation` | Stage progress + agent panel + streaming log | Debugging/curiosity |
| `verbose` | Full detail: progress + agents + streaming log + conversation feed | Deep debugging |

**Example: `--activity=status` (default)**

```
 [✓] Requirements (23s)
 [>] Design — 2 agents active
 [ ] Implementation
 [ ] Testing
 [ ] Deployment
 [ ] Monitoring

 Agent Activity
 ● System Architect    thinking   Designing database schema for user auth...
 ● API Designer        idle
```

**Example: `--activity=conversation`**

Adds a real-time streaming log panel below the agent panel, showing agent thinking, output, tool calls, token usage, and cache hit info:

```
 ╭─ Agent Stream ──────────────────────────────────────────────────────────╮
 │ Time       Agent                  Event        Output                   │
 │ 14:02:31   ArchitectureResult     thinking     Analyzing: System: You   │
 │                                                are the System Archit... │
 │ 14:02:58   ArchitectureResult     message      3 services, 12 endpoi   │
 │                                                nts (4,230tok, cache:    │
 │                                                3,100)                   │
 │ 14:03:01   APIDesignResult        thinking     Analyzing: Given a PRD   │
 │                                                and architecture...      │
 │ 14:03:15   APIDesignResult        tool call    Using tool: openapi_va   │
 │                                                lidator                  │
 ╰─────────────────────────────────────────────────────────────────────────╯
```

The streaming log shows up to 30 entries and displays token counts with cache savings inline.

**Example: `--activity=verbose`**

Shows everything from `conversation` mode plus a scrolling conversation feed with agent-to-agent handoffs:

```
 Conversation
 14:02:31  Design Supervisor → System Architect
           "Generate system architecture for auth module."

 14:02:58  System Architect → API Designer
           Handed off: system_architecture.yaml (3 services, 12 endpoints)
```

The conversation feed is a ring buffer (last 50 messages) to keep memory bounded.

---

## API Reference

The REST API is available when the server is running (`colette serve`). Interactive docs at `/api/v1/docs` (Swagger) and `/api/v1/redoc`.

### Authentication

All API requests require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/projects
```

### Endpoints

#### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/health/ready` | Readiness check |

#### Projects

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/projects` | Create project and start pipeline |
| GET | `/api/v1/projects` | List projects (paginated) |
| GET | `/api/v1/projects/{id}` | Get project by ID |

**Create project request:**

```json
{
  "name": "my-todo-app",
  "description": "A todo list web application",
  "user_request": "Build a todo list web app with user auth, CRUD, filtering"
}
```

#### Pipelines

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/projects/{id}/pipeline` | Get pipeline status |
| GET | `/api/v1/projects/{id}/pipeline/events` | SSE stream of progress events |
| POST | `/api/v1/projects/{id}/pipeline/resume` | Resume paused pipeline |

#### Approvals

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/approvals/{id}/approve` | Approve gate request |
| POST | `/api/v1/approvals/{id}/reject` | Reject gate request |

#### Artifacts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/projects/{id}/artifacts/download` | Download artifacts as zip |

#### WebSocket

| Path | Description |
|------|-------------|
| `/api/v1/ws/{project_id}` | Real-time pipeline updates |

---

## Programmatic Usage (Python)

### Run a pipeline directly

```python
import asyncio
from colette.orchestrator.runner import PipelineRunner

async def main():
    runner = PipelineRunner()

    result = await runner.run(
        "my-todo-app",
        user_request="""
        Build a todo list web application with:
        - User registration and login (email + password)
        - Create, read, update, delete todos
        - Mark todos as complete
        - Filter by status (all, active, completed)
        - PostgreSQL database
        - REST API with OpenAPI documentation
        """,
    )

    # Result contains the full pipeline state
    print(f"Status: {result['stage_statuses']}")
    print(f"Completed: {result['completed_at']}")

    # Access handoffs from each stage
    requirements = result["handoffs"].get("requirements")
    design = result["handoffs"].get("design")
    implementation = result["handoffs"].get("implementation")
    testing = result["handoffs"].get("testing")
    deployment = result["handoffs"].get("deployment")

asyncio.run(main())
```

### Skip stages

```python
result = await runner.run(
    "my-app",
    user_request="...",
    skip_stages=["monitoring"],  # skip monitoring stage
)
```

### Monitor progress

```python
# Check if a pipeline is running
runner.is_active("my-app")

# Get current progress
progress = await runner.get_progress("my-app")
print(progress.stage, progress.status)
```

### Resume after human approval

When a stage requires human approval (T0/T1 tier), the pipeline pauses:

```python
result = await runner.resume(
    "my-app",
    update_values={"approval_decisions": [
        {
            "request_id": "...",
            "status": "approved",
            "reviewer_id": "you@example.com",
            "comments": "LGTM",
        }
    ]},
)
```

### Custom settings

```python
from colette.config import Settings

settings = Settings(
    default_execution_model="gpt-5.4-mini",
    agent_timeout_seconds=300,
    supervisor_context_budget=80_000,
)
runner = PipelineRunner(settings=settings)
```

---

## Configuration Reference

All settings use the `COLETTE_` prefix and load from `.env` or environment variables.

### LLM Models

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_DEFAULT_PLANNING_MODEL` | Planning/architecture (Opus) | `claude-opus-4-6-20250610` |
| `COLETTE_DEFAULT_EXECUTION_MODEL` | Code generation (Sonnet) | `claude-sonnet-4-6-20250514` |
| `COLETTE_DEFAULT_VALIDATION_MODEL` | Scanning/validation (Haiku) | `claude-haiku-4-5-20251001` |
| `COLETTE_LITELLM_BASE_URL` | LiteLLM proxy URL | `http://localhost:4000` |

**Fallback chains** (tried in order on primary model failure):

| Tier | Primary | Fallback 1 | Fallback 2 |
|------|---------|-----------|-----------|
| Planning | Claude Opus | GPT-5.4 | Gemini 2.5 Pro |
| Execution | Claude Sonnet | GPT-5.4 Mini | Gemini 2.5 Flash |
| Validation | Claude Haiku | GPT-5.4 Mini | Gemini 2.5 Flash |

### LLM Cost Optimization

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_PROMPT_CACHING_ENABLED` | Enable Anthropic prompt caching (90% savings on cached reads) | `true` |
| `COLETTE_LLM_TIMEOUT_SECONDS` | LLM request timeout | `120` |
| `COLETTE_LLM_MAX_RETRIES` | Retries on transient failure | `2` |
| `COLETTE_LLM_MAX_CONCURRENCY` | Max concurrent LLM calls (prevents rate-limit storms) | `2` |
| `COLETTE_COST_OVERRUN_MULTIPLIER` | Alert when agent cost exceeds baseline x this | `2.0` |

**Prompt caching:** When enabled, system prompts (including JSON schemas) are marked with Anthropic's `cache_control: ephemeral`. The first call writes to cache (1.25x cost), subsequent calls within 5 minutes read from cache at 0.1x cost. This is especially effective for Colette's agents since each output type uses the same system prompt + schema across calls.

**Three-tier model selection** automatically routes to the right cost/capability tradeoff:
- **Planning tier** (Opus): supervisors, architects -- highest reasoning quality
- **Execution tier** (Sonnet): all code-generating agents -- best code quality/cost ratio
- **Validation tier** (Haiku): scanners, validators -- cheapest for simple checks

### Infrastructure

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://colette:colette@localhost:5432/colette` |
| `COLETTE_REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `COLETTE_NEO4J_URI` | Neo4j URI | `bolt://localhost:7687` |
| `COLETTE_NEO4J_USER` | Neo4j user | `neo4j` |
| `COLETTE_NEO4J_PASSWORD` | Neo4j password | `colette-dev` |

### Agent Behavior

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_AGENT_MAX_ITERATIONS` | Max reasoning loops per agent | `25` |
| `COLETTE_AGENT_TIMEOUT_SECONDS` | Agent timeout (seconds) | `600` |
| `COLETTE_SUPERVISOR_CONTEXT_BUDGET` | Supervisor token budget | `100000` |
| `COLETTE_SPECIALIST_CONTEXT_BUDGET` | Specialist token budget | `60000` |
| `COLETTE_VALIDATOR_CONTEXT_BUDGET` | Validator token budget | `30000` |
| `COLETTE_MAX_CONCURRENT_PIPELINES` | Parallel pipeline limit | `5` |

### Memory & RAG

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_COMPACTION_THRESHOLD` | Context compaction trigger | `0.70` |
| `COLETTE_RAG_CHUNK_SIZE` | Chunk size for retrieval | `512` |
| `COLETTE_RAG_FAITHFULNESS_THRESHOLD` | RAG quality threshold | `0.85` |
| `COLETTE_KNOWLEDGE_GRAPH_ENABLED` | Enable Neo4j knowledge graph | `true` |
| `COLETTE_COHERE_API_KEY` | Cohere reranker API key | *(empty)* |
| `COLETTE_MEMORY_DECAY_ENABLED` | Enable memory decay | `false` |

### Human-in-the-Loop

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_HIL_CONFIDENCE_THRESHOLD` | Below this triggers escalation | `0.60` |
| `COLETTE_HIL_CONFIDENCE_FLAG_THRESHOLD` | Below this flags for review, above auto-approves | `0.85` |
| `COLETTE_HIL_T0_SLA_SECONDS` | T0 approval SLA | `3600` (1h) |
| `COLETTE_HIL_T1_SLA_SECONDS` | T1 approval SLA | `14400` (4h) |

### Pipeline

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_CHECKPOINT_BACKEND` | `memory` (dev) or `postgres` (prod) | `memory` |
| `COLETTE_CHECKPOINT_DB_URL` | Checkpoint DB (falls back to DATABASE_URL) | *(empty)* |
| `COLETTE_HANDOFF_MAX_CHARS` | Max handoff size | `128000` |

### Security

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_RBAC_ENABLED` | Enable role-based access control | `true` |
| `COLETTE_RBAC_DEFAULT_ROLE` | Default user role | `observer` |
| `COLETTE_SECRET_FILTER_ENABLED` | Filter secrets from LLM output | `true` |
| `COLETTE_PROMPT_INJECTION_DEFENSE_ENABLED` | Enable prompt injection defense | `true` |
| `COLETTE_MCP_ALLOW_UNVERIFIED` | Allow unverified MCP servers | `false` |

### API Server

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_HOST` | Bind host | `0.0.0.0` |
| `COLETTE_PORT` | Bind port | `8000` |
| `COLETTE_WORKERS` | Number of workers | `1` |
| `COLETTE_API_RATE_LIMIT_PER_MINUTE` | Rate limit (requests/min) | `100` |
| `COLETTE_CORS_ORIGINS` | CORS allowed origins | `["*"]` |

### Observability

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_LOG_LEVEL` | Logging level | `INFO` |
| `COLETTE_LOG_FORMAT` | Log format | `json` |
| `COLETTE_OTEL_SERVICE_NAME` | OpenTelemetry service name | `colette` |
| `COLETTE_OTEL_EXPORTER_ENDPOINT` | OTEL exporter endpoint | `http://localhost:4318` |

---

## Pipeline Stages

### 1. Requirements Stage

**Input:** Your natural language request

**Output (`RequirementsToDesignHandoff`):**
- Product Requirements Document (PRD)
- User stories with acceptance criteria
- Non-functional requirements (performance, security, scalability)
- Technology constraints
- Domain research findings

### 2. Design Stage

**Input:** Requirements handoff

**Output (`DesignToImplementationHandoff`):**
- Architecture summary and tech stack decisions
- OpenAPI specification (full JSON spec)
- Database entity specifications (fields, indexes, relationships)
- UI component specifications with routes
- Architecture Decision Records (ADRs)
- Security design
- Implementation task breakdown

### 3. Implementation Stage

**Input:** Design handoff

**Output (`ImplementationToTestingHandoff`):**
- Generated source files (React/Next.js frontend, FastAPI/Express backend, ORM models)
- Migration files
- Environment variable definitions
- Implemented endpoint list
- Cross-review findings (API contract mismatches between frontend/backend)

Agents run in parallel: Frontend, Backend, and DB Engineer generate code simultaneously. A cross-review step checks for integration issues.

### 4. Testing Stage

**Input:** Implementation handoff

**Output (`TestingToDeploymentHandoff`):**
- Unit test files (pytest/Jest)
- Integration test files (API, contract, E2E stubs)
- Coverage metrics (line and branch)
- Security scan findings (SAST, dependency CVEs, accessibility)
- Deploy readiness score (0-100)
- Blocking issues list

### 5. Deployment Stage

**Input:** Testing handoff

**Output (`DeploymentToMonitoringHandoff`):**
- CI/CD pipeline files (GitHub Actions)
- Dockerfiles (multi-stage, non-root)
- Docker Compose configurations
- Kubernetes manifests (when applicable)
- Rollback command
- SLO targets
- Deployment targets with health check URLs

### 6. Monitoring Stage

**Input:** Deployment handoff

**Output:** Dashboard configs, alert rules, SLO tracking setup.

---

## Human Oversight

Colette uses a four-tier approval model:

| Tier | When | Behavior |
|------|------|----------|
| **T0 -- Critical** | Production deploys, DB migrations, security architecture | Pipeline **pauses** -- human approval required |
| **T1 -- High** | API contract changes, new dependencies, infra changes | Pipeline **pauses** -- human review required |
| **T2 -- Moderate** | Code generation, test writing | Auto-approves if confidence >= 0.85, otherwise pauses |
| **T3 -- Routine** | Linting, formatting, log analysis | Fully autonomous |

### Confidence Gating (T2)

For T2 actions, agents report a confidence score:
- **>= 0.85**: Auto-approved
- **0.60 - 0.84**: Flagged for review, pipeline pauses
- **< 0.60**: Escalated, pipeline pauses

### Responding to Approvals

**Via CLI:**

```bash
# Approve
uv run colette approve <approval-id> --comment "Looks good"

# Reject
uv run colette reject <approval-id> --reason "Add input validation first"
```

**Via API:**

```bash
# Approve
curl -X POST http://localhost:8000/api/v1/approvals/<id>/approve \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"reviewer_id": "you@example.com", "comments": "LGTM"}'

# Reject
curl -X POST http://localhost:8000/api/v1/approvals/<id>/reject \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"reviewer_id": "you@example.com", "reason": "Needs security review"}'
```

---

## Quality Gates

Quality gates run between stages to enforce minimum standards. If a gate fails, the pipeline can pause or retry.

| Gate | Between | Key Criteria |
|------|---------|-------------|
| Requirements | Requirements -> Design | User stories present, NFRs defined |
| Design | Design -> Implementation | Architecture specified, OpenAPI spec present |
| Implementation | Implementation -> Testing | Files generated, no CRITICAL review findings |
| Testing | Testing -> Deployment | Coverage >= 80%, no CRITICAL security, contracts pass |
| Staging | Deployment -> Monitoring | Targets defined, health checks configured, rollback ready |
| Production | Before production deploy | Human T0 approval required |

---

## Extending Colette

### Adding a New Agent

Each agent follows the same pattern:

```python
# src/colette/stages/<stage>/<agent_name>.py

from pydantic import BaseModel, Field
from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier

class MyAgentResult(BaseModel, frozen=True):
    """Structured output -- frozen for immutability."""
    files: list[GeneratedFile] = Field(default_factory=list)
    notes: str = ""

async def run_my_agent(context: str, *, settings: Settings) -> MyAgentResult:
    return await invoke_structured(
        system_prompt="You are ...",
        user_content=context,
        output_type=MyAgentResult,
        settings=settings,
        model_tier=ModelTier.EXECUTION,  # Sonnet
    )
```

Key conventions:
- **Frozen Pydantic models** for all agent outputs
- **`invoke_structured()`** for LLM calls with JSON schema enforcement
- **`ModelTier`** selects the model: `PLANNING` (Opus), `EXECUTION` (Sonnet), `VALIDATION` (Haiku)
- **structlog** for all logging

### Adding a New Quality Gate

```python
# src/colette/gates/my_gate.py

from colette.gates.base import QualityGate

class MyGate(QualityGate):
    name = "my_gate"

    def evaluate(self, handoff_data: dict) -> QualityGateResult:
        passed = handoff_data.get("score", 0) >= 80
        return QualityGateResult(
            gate_name=self.name,
            passed=passed,
            criteria_results={"score_threshold": passed},
        )
```

Register it in `src/colette/gates/__init__.py`.

---

## Troubleshooting

### Pipeline fails at a stage

Check the error log in the pipeline result:

```python
for error in result.get("error_log", []):
    print(error)
```

Via CLI:

```bash
uv run colette logs <project-id> --stage <failed-stage>
```

### Quality gate blocks progression

Check what criteria failed:

```python
gate_results = result.get("quality_gate_results", {})
for gate_name, gate_result in gate_results.items():
    if not gate_result["passed"]:
        print(f"{gate_name}: {gate_result['failure_reasons']}")
```

### LLM calls fail

Colette has automatic fallback chains. If the primary model fails, it tries fallbacks in order. Check that at least one provider API key is configured in `.env`.

Verify your config:

```bash
uv run colette config validate
```

### Server won't start

1. Check services are running: `docker compose ps`
2. Check database connectivity: `docker compose logs postgres`
3. Validate config: `uv run colette config validate`
4. Check port conflicts: ensure 8000 is free

### Tests fail locally

```bash
# Unit tests (no services needed)
make test-unit

# Integration tests require Docker services
make docker-up
make test-integration
```

### Docker services won't start

```bash
# Check status
docker compose ps

# View logs
docker compose logs postgres
docker compose logs redis
docker compose logs neo4j

# Restart
make docker-down
make docker-up
```

---

## Development

### Make targets

```bash
make install          # Install all dependencies
make dev              # Install + create .env from template
make lint             # Run ruff linter
make format           # Auto-format with ruff
make typecheck        # Run mypy strict mode
make test             # Run all tests with coverage (80% min)
make test-unit        # Unit tests only
make security         # bandit + pip-audit
make check            # lint + typecheck + test + security
make docker-up        # Start postgres, redis, neo4j
make docker-down      # Stop services
make docker-build     # Build colette container image
make clean            # Remove build artifacts
make docs-serve       # Serve docs locally (mkdocs)
make docs-build       # Build static docs site
```

### Project structure

```
src/colette/
  __init__.py           # Package root, __version__
  cli.py                # CLI entry point (Click)
  cli_ui.py             # Rich terminal rendering + streaming log panel
  cli_review.py         # Textual TUI for interactive approval review
  config.py             # Settings via pydantic-settings
  schemas/              # Typed handoff schemas between stages
    requirements.py     # RequirementsToDesignHandoff
    design.py           # DesignToImplementationHandoff
    implementation.py   # ImplementationToTestingHandoff
    testing.py          # TestingToDeploymentHandoff
    deployment.py       # DeploymentToMonitoringHandoff
    common.py           # Shared models
  orchestrator/
    runner.py           # PipelineRunner -- main entry point
    pipeline.py         # LangGraph DAG construction
    state.py            # PipelineState definition
    progress.py         # Progress event tracking
    event_bus.py        # In-process event bus for pipeline events
    agent_presence.py   # Agent presence tracking (Slack-style activity feed)
  stages/
    requirements/       # Analyst + Researcher agents
    design/             # Architect + API Designer + UI/UX agents
    implementation/     # Frontend + Backend + DB Engineer agents
    testing/            # Unit Tester + Integration Tester + Security Scanner
    deployment/         # CI/CD Engineer + Infrastructure Engineer
    monitoring/         # Observability + Incident Response
  api/                  # FastAPI REST API
    app.py              # Application factory
    routes/             # Endpoint handlers
    middleware.py       # Rate limiting, request IDs, graceful degradation
    schemas.py          # API request/response models
    deps.py             # Dependency injection
  db/                   # Database models and repositories
  memory/               # Hot/warm/cold memory tiers, RAG pipeline
  gates/                # Quality gate implementations
  human/                # Approval routing, confidence scoring
  tools/                # MCP tool wrappers
  llm/                  # LiteLLM gateway, structured output, prompt caching
  security/             # RBAC, audit, secret filtering
  observability/        # Logging, OpenTelemetry tracing
tests/
  conftest.py           # Shared fixtures
  unit/                 # Fast, no external deps
  integration/          # Requires services
  e2e/                  # Full pipeline tests
```

### Running with Docker

```bash
# Build the image
make docker-build

# Run (requires backing services)
docker run -p 8000:8000 --env-file .env colette:latest
```

---

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Scaffolding | Done | Project structure, CI, Docker |
| 2. Core Schemas | Done | Pydantic handoff schemas, pipeline state |
| 3. Orchestration | Done | LangGraph DAG, quality gates, human-in-the-loop |
| 4. Requirements + Design | Done | Requirements and Design agents |
| 5. Implementation | Done | Frontend, Backend, DB Engineer agents |
| 6. Testing + Deployment | Done | Testing and Deployment agents |
| 7. Monitoring | Planned | Observability and incident response agents |
| 8. REST API + CLI | Done | FastAPI server, Click CLI, Rich UI, Textual TUI for approvals |
| 9. Cost Optimization | Done | Anthropic prompt caching, three-tier models, token budgets, streaming agent log |
| 10. Hardening | Planned | Performance tuning, security audit, batch API |
