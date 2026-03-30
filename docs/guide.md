# Colette User Guide

Colette is a multi-agent AI system that turns a natural language description into a fully built web application -- from requirements through deployment. This guide covers setup, usage, configuration, and how to work with the system.

## How It Works

You provide a description of the app you want. Colette runs it through a six-stage pipeline, each managed by a supervisor agent with specialist agents:

```
Your Request
    │
    ▼
1. Requirements ─── Analyst + Domain Researcher
    │                Produces: PRD, user stories, NFRs
    ▼
2. Design ───────── System Architect + API Designer + UI/UX Designer
    │                Produces: architecture, OpenAPI spec, DB schema, UI components
    ▼
3. Implementation ── Frontend Dev + Backend Dev + DB Engineer
    │                Produces: React/Next.js code, API routes, migrations, seed data
    ▼
4. Testing ──────── Unit Tester + Integration Tester + Security Scanner
    │                Produces: test suites, coverage report, security findings, readiness score
    ▼
5. Deployment ───── CI/CD Engineer + Infrastructure Engineer
    │                Produces: GitHub Actions, Dockerfiles, K8s manifests, rollback config
    ▼
6. Monitoring ───── Observability Agent + Incident Response
                     Produces: dashboards, alerts, SLO tracking
```

Each stage passes its output to the next via a **typed handoff schema** -- structured data, not free text. Quality gates between stages enforce minimum standards (coverage thresholds, no critical security findings, etc.).

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker and Docker Compose (for dev services)
- An LLM API key (Anthropic, OpenAI, or Google)

### Installation

```bash
git clone https://github.com/Jss-on/colette.git
cd colette

# Install dependencies
make install

# Create .env from template
make dev
```

### Configure API Keys

Edit `.env` and add at least one LLM provider key:

```bash
# Required: at least one
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

### Start Services

Colette uses PostgreSQL (with pgvector), Redis, and optionally Neo4j:

```bash
make docker-up
```

### Verify

```bash
make check   # lint + typecheck + test + security
```

## Running a Pipeline

### Programmatic Usage (Python)

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

### Skip Stages

Skip stages you don't need:

```python
result = await runner.run(
    "my-app",
    user_request="...",
    skip_stages=["monitoring"],  # skip monitoring stage
)
```

### Monitor Progress

```python
# Check if a pipeline is running
runner.is_active("my-app")

# Get current progress
progress = await runner.get_progress("my-app")
print(progress.stage, progress.status)
```

### Resume After Human Approval

When a stage requires human approval (T0/T1 tier), the pipeline pauses:

```python
# Pipeline pauses at deployment stage (production deploy = T0)
# Review the proposed action, then resume:
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

## What Each Stage Produces

### 1. Requirements Stage

**Input:** Your natural language request

**Output (`RequirementsToDesignHandoff`):**
- Product Requirements Document (PRD)
- User stories with acceptance criteria
- Non-functional requirements (performance, security, scalability)
- Technology constraints
- Domain research findings (when relevant)

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

**Agents run in parallel:** Frontend, Backend, and DB Engineer generate code simultaneously. A cross-review step then checks for integration issues.

### 4. Testing Stage

**Input:** Implementation handoff

**Output (`TestingToDeploymentHandoff`):**
- Unit test files (pytest/Jest)
- Integration test files (API, contract, E2E stubs)
- Coverage metrics (line and branch)
- Security scan findings (SAST, dependency CVEs, accessibility)
- Deploy readiness score (0-100)
- Blocking issues list

**Quality gate criteria:**
- Line coverage >= 80%
- Branch coverage >= 70%
- No CRITICAL security findings
- Contract tests pass (API matches OpenAPI spec)

**Agent execution:** Unit Tester and Integration Tester run in parallel. Security Scanner runs after (needs test context). Security scanner failure is non-blocking.

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

**Quality gate criteria:**
- Pipeline files generated
- Docker images defined
- Rollback configured
- Staging auto-deploy configured
- Production gate (manual approval) configured

**Agent execution:** CI/CD Engineer and Infrastructure Engineer run in parallel. Both are required -- failure in either stops the pipeline.

### 6. Monitoring Stage

**Input:** Deployment handoff

**Output:** Dashboard configs, alert rules, SLO tracking setup. *(Currently a stub -- Phase 7 will implement this stage.)*

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
- **>= 0.85**: Auto-approved, no human intervention
- **0.60 - 0.84**: Flagged for review, pipeline pauses
- **< 0.60**: Escalated, pipeline pauses

Configure thresholds in `.env`:

```bash
COLETTE_HIL_CONFIDENCE_THRESHOLD=0.60
COLETTE_HIL_CONFIDENCE_FLAG_THRESHOLD=0.85
```

## Configuration Reference

All settings use the `COLETTE_` prefix and load from `.env`:

### LLM Models

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_DEFAULT_PLANNING_MODEL` | Planning/architecture (Opus) | `claude-opus-4-6-20250610` |
| `COLETTE_DEFAULT_EXECUTION_MODEL` | Code generation (Sonnet) | `claude-sonnet-4-6-20250514` |
| `COLETTE_DEFAULT_VALIDATION_MODEL` | Scanning/validation (Haiku) | `claude-haiku-4-5-20251001` |
| `COLETTE_LITELLM_BASE_URL` | LiteLLM proxy URL | `http://localhost:4000` |

### Infrastructure

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://colette:colette@localhost:5432/colette` |
| `COLETTE_REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `COLETTE_NEO4J_URI` | Neo4j (knowledge graph) | `bolt://localhost:7687` |

### Agent Behavior

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_AGENT_MAX_ITERATIONS` | Max reasoning loops per agent | `25` |
| `COLETTE_AGENT_TIMEOUT_SECONDS` | Agent timeout | `600` |
| `COLETTE_SUPERVISOR_CONTEXT_BUDGET` | Supervisor token budget | `100000` |
| `COLETTE_SPECIALIST_CONTEXT_BUDGET` | Specialist token budget | `60000` |
| `COLETTE_MAX_CONCURRENT_PIPELINES` | Parallel pipeline limit | `5` |

### Memory & RAG

| Variable | Description | Default |
|----------|-------------|---------|
| `COLETTE_COMPACTION_THRESHOLD` | Context compaction trigger | `0.70` |
| `COLETTE_RAG_CHUNK_SIZE` | Chunk size for retrieval | `512` |
| `COLETTE_RAG_FAITHFULNESS_THRESHOLD` | RAG quality threshold | `0.85` |
| `COLETTE_KNOWLEDGE_GRAPH_ENABLED` | Enable Neo4j knowledge graph | `true` |
| `COLETTE_COHERE_API_KEY` | Cohere reranker API key | *(empty)* |

See `src/colette/config.py` for the complete schema.

## Quality Gates

Quality gates run between stages to enforce minimum standards. If a gate fails, the pipeline can pause or retry:

| Gate | Between | Key Criteria |
|------|---------|-------------|
| Requirements Gate | Requirements -> Design | User stories present, NFRs defined |
| Design Gate | Design -> Implementation | Architecture specified, OpenAPI spec present |
| Implementation Gate | Implementation -> Testing | Files generated, no CRITICAL review findings |
| Testing Gate | Testing -> Deployment | Coverage >= 80%, no CRITICAL security, contracts pass |
| Staging Gate | Deployment -> Monitoring | Targets defined, health checks configured, rollback ready |
| Production Gate | Before production deploy | Human T0 approval required |

## Project Structure

```
src/colette/
  cli.py              # CLI entry point
  config.py           # Settings (env vars)
  schemas/            # Typed handoff schemas between stages
    requirements.py   # RequirementsToDesignHandoff
    design.py         # DesignToImplementationHandoff
    implementation.py # ImplementationToTestingHandoff
    testing.py        # TestingToDeploymentHandoff
    deployment.py     # DeploymentToMonitoringHandoff
    common.py         # Shared models (SecurityFinding, SuiteResult, etc.)
  orchestrator/
    runner.py         # PipelineRunner — main entry point
    pipeline.py       # LangGraph DAG construction
    state.py          # PipelineState definition
  stages/
    requirements/     # Analyst + Researcher agents
    design/           # Architect + API Designer + UI/UX agents
    implementation/   # Frontend + Backend + DB Engineer agents
    testing/          # Unit Tester + Integration Tester + Security Scanner
    deployment/       # CI/CD Engineer + Infrastructure Engineer
    monitoring/       # Observability + Incident Response (stub)
  memory/             # Hot/warm/cold memory tiers, RAG pipeline
  gates/              # Quality gate implementations
  human/              # Approval routing, confidence scoring, SLA tracking
  tools/              # MCP tool wrappers (git, filesystem, terminal)
  llm/                # LiteLLM gateway, structured output parsing
  observability/      # OpenTelemetry tracing, metrics, callbacks
```

## Extending Colette

### Adding a New Agent

Each agent follows the same pattern:

```python
# src/colette/stages/<stage>/<agent_name>.py

from pydantic import BaseModel, Field
from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier

class MyAgentResult(BaseModel, frozen=True):
    """Structured output — frozen for immutability."""
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

## Troubleshooting

### Pipeline fails at a stage

Check the error log in the pipeline result:

```python
for error in result.get("error_log", []):
    print(error)
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

Colette has automatic fallback chains. If the primary model fails, it tries fallbacks in order:

- Planning: Claude Opus -> GPT-5.4 -> Gemini 2.5 Pro
- Execution: Claude Sonnet -> GPT-5.4 Mini -> Gemini 2.5 Flash
- Validation: Claude Haiku -> GPT-5.4 Mini -> Gemini 2.5 Flash

Check that at least one provider API key is configured in `.env`.

### Tests fail locally

```bash
# Run just unit tests (no services needed)
make test-unit

# Integration tests require Docker services
make docker-up
make test-integration
```

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Scaffolding | Done | Project structure, CI, Docker |
| 2. Core Schemas | Done | Pydantic handoff schemas, pipeline state |
| 3. Orchestration | Done | LangGraph DAG, quality gates, human-in-the-loop |
| 4. Requirements + Design | Done | First real agents |
| 5. Implementation | Done | Frontend, Backend, DB Engineer agents |
| 6. Testing + Deployment | Done | Unit/Integration/Security testing, CI/CD + Infra agents |
| 7. Monitoring | Planned | Observability and incident response agents |
| 8. Memory | Planned | Warm/cold memory tiers, RAG pipeline |
| 9. Hardening | Planned | Performance, security audit, documentation |
