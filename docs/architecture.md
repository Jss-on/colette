# Architecture

## Three-Layer Design

```
+---------------------------------------------------+
|              Orchestration Layer                    |
|  LangGraph DAG — Project Orchestrator + 6 stages  |
+---------------------------------------------------+
|                Memory Layer                         |
|  Hot (context) → Warm (Mem0/pgvector) → Cold (S3) |
+---------------------------------------------------+
|           Context Management Layer                  |
|  Token budgets, RAG, Morph Compact at 70%          |
+---------------------------------------------------+
```

### Orchestration Layer (LangGraph)

The SDLC pipeline is modeled as a directed acyclic graph.  A **Project Orchestrator** decomposes user requests into pipeline stages, delegating to **Stage Supervisors**, each managing 2-4 specialist agents.

### Memory Layer (Hybrid)

| Tier | Technology | Purpose |
|------|-----------|---------|
| Hot | LangGraph context window | Active conversation state |
| Warm | Mem0 + Graphiti + pgvector | Project memory, knowledge graph, RAG |
| Cold | S3-compatible archive | Long-term storage, audit trail |

### Context Management Layer

Each agent operates within a **token budget**:

- Supervisors: 100K tokens
- Specialists: 60K tokens
- Validators: 30K tokens

Morph Compact triggers at 70% utilization.  RAG uses hybrid retrieval (BM25 + dense vectors + Cohere rerank).

## Six-Stage Pipeline

```
User Request
    │
    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Requirements │ ──▶ │    Design    │ ──▶ │Implementation│
│  Supervisor  │     │  Supervisor  │     │  Supervisor  │
│  + Analyst   │     │  + Architect │     │  + Frontend  │
│  + Researcher│     │  + API Des.  │     │  + Backend   │
│              │     │  + UI/UX     │     │  + DB Eng.   │
└──────────────┘     └──────────────┘     └──────────────┘
                                                │
    ┌───────────────────────────────────────────┘
    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Testing    │ ──▶ │  Deployment  │ ──▶ │  Monitoring  │
│  Supervisor  │     │  Supervisor  │     │  Supervisor  │
│  + Unit Test │     │  + CI/CD Eng │     │  + Observ.   │
│  + Int. Test │     │  + Infra Eng │     │  + Incident  │
│  + Security  │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

Inter-stage communication uses **typed Pydantic handoff schemas** with versioning and size enforcement.  See the [Schemas API reference](api/schemas.md).

## Human Oversight Tiers

| Tier | Level | Examples | Behavior |
|------|-------|----------|----------|
| T0 | Critical | Production deploys, DB migrations | Human **required** |
| T1 | High | API contract changes, new dependencies | Human **review** |
| T2 | Moderate | Code generation, test writing | Confidence-gated (escalate if < 0.60) |
| T3 | Routine | Linting, formatting, log analysis | Fully **autonomous** |

## Model Assignment

| Tier | Model | Agents |
|------|-------|--------|
| Planning | Opus | Orchestrator, Design Supervisor, System Architect |
| Execution | Sonnet | All other agents |
| Validation | Haiku | Scanners, validators |

See the [LLM Gateway API reference](api/llm.md) for model registry and fallback chain details.

## Further Reading

- [Full System Architecture Spec](MultiAgent_SDLC_System_Architecture.md)
- [Software Requirements Specification](Colette_Software_Requirements_Specification.md)
- [Implementation Guide](Complete_Guide_to_Building_AI_Agent_Systems.md)
