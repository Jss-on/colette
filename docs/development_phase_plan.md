# Colette Development Phase Plan

## Context

Colette is a multi-agent AI system (164 requirements, 16 agents, 6 SDLC stages) currently scaffolded but with zero implementation. This plan decomposes v1.0 into 9 incrementally deliverable phases, ordered by dependency. Each phase produces a testable increment. The plan covers all 116 MUST, 28/29 SHOULD, and 6/7 COULD requirements.

---

## Phase Dependency Graph

```
Phase 0: Foundation (Schemas, Config, LLM Gateway)           ~1 week,  M
  |
  v
Phase 1: Agent Framework + Tool Abstraction                   ~2 weeks, L
  |
  +-----------+
  v            v
Phase 2: Memory Layer          Phase 3: Pipeline Orchestration
(Hot/Warm/Cold, RAG)           (StateGraph, Gates, HIL)
~3 weeks, XL                   ~2-3 weeks, XL
  |            |
  +-----+------+
        v
Phase 4: Requirements + Design Stages (first real agents)     ~3 weeks, XL
  |
  v
Phase 5: Implementation Stage (code generation)               ~3 weeks, XL
  |
  v
Phase 6: Testing + Deployment Stages                          ~3 weeks, XL
  |
  v
Phase 7: Monitoring + Security Hardening + Observability      ~2 weeks, L
  |
  v
Phase 8: REST API + CLI + Web UI + Production Readiness       ~2-3 weeks, L
```

**Note:** Phases 2 and 3 can proceed in parallel by separate engineers.

---

## Phase 0: Foundation Layer (Schemas, Config, LLM Gateway)

**Goal:** Typed data contracts, configuration, and LLM abstraction everything else depends on.

**Complexity:** M | **Duration:** ~1 week

### Requirements (10)
| Priority | IDs |
|----------|-----|
| MUST (8) | FR-ORC-020 (typed handoffs), FR-ORC-021 (schema versioning), FR-ORC-022 (content filtering), FR-ORC-024 (size limits), FR-TL-006 (LLM gateway), FR-ORC-014 (model fallback), FR-MEM-004 (context budgets), FR-ORC-017 (tool count limit) |
| SHOULD (2) | FR-ORC-025 (handoff latency <200ms), FR-TL-007 (prompt caching) |

### Key Deliverables
1. **Handoff schemas** (`src/colette/schemas/`) -- 6 inter-stage Pydantic models + common sub-models
   - `requirements.py`, `design.py`, `implementation.py`, `testing.py`, `deployment.py`, `common.py`
   - Extend `base.py` with token counting, size validation, version compatibility
2. **Agent config model** (`src/colette/schemas/agent_config.py`) -- AgentConfig with tool count validator, budget allocation
3. **LLM gateway** (`src/colette/llm/`) -- `gateway.py` (ChatLiteLLM factory with fallbacks), `models.py` (model registry), `token_counter.py`
4. **Config extension** -- LLM fallback chains, model assignments per role, embedding/reranker models

### Verification
- All 6 handoff schemas validate/reject correctly; version mismatch produces structured error
- Handoff >8K tokens triggers compression or explicit error
- `create_chat_model()` returns ChatModel with fallback chain
- AgentConfig rejects >5 tools
- `make check` passes

### Risks
- ChatLiteLLM API may differ from LangChain ChatModel interface -> write integration spike test
- Token counting accuracy across providers -> accept +/-5%, track actual via usage_metadata

---

## Phase 1: Agent Framework + Tool Abstraction

**Goal:** Reusable agent instantiation, MCP tool wrappers, circuit breaker, error recovery, observability.

**Complexity:** L | **Duration:** ~2 weeks | **Depends on:** Phase 0

### Requirements (12)
| Priority | IDs |
|----------|-----|
| MUST (11) | FR-ORC-010 (agent instantiation), FR-ORC-011 (iteration limits), FR-ORC-012 (timeout), FR-ORC-013 (error recovery), FR-ORC-015 (observability), FR-ORC-018 (circuit breaker), FR-TL-001 (MCP protocol), FR-TL-002 (core MCP servers), FR-TL-003 (tool access control), FR-TL-004 (tool sanitization), FR-TL-005 (tool auditing) |
| SHOULD (1) | FR-ORC-016 (hot-swap config) |

### Key Deliverables
1. **Agent factory** (`src/colette/orchestrator/agent_factory.py`) -- wraps `create_react_agent()` with timeout, recursion_limit, circuit breaker, escalation, OTel spans
2. **Circuit breaker** (`src/colette/orchestrator/circuit_breaker.py`) -- immutable dataclass, rolling window, 3 failures/5min threshold
3. **Error recovery** (`src/colette/orchestrator/error_recovery.py`) -- 4-step escalation chain: retry -> compact -> supervisor -> human
4. **MCP tool wrappers** (`src/colette/tools/`) -- `base.py` (MCPBaseTool with sanitization), `filesystem.py`, `git.py`, `terminal.py`
5. **Observability** (`src/colette/observability/`) -- `tracing.py` (OTel provider), `callbacks.py` (LangChain handler), `metrics.py` (token/cost counters)

### Verification
- Agent stops at recursion_limit and escalates
- Agent times out and preserves state
- Circuit breaker blocks after 3 failures in 5 minutes
- Escalation chain executes all 4 steps in order
- OTel spans contain agent_id, model, tokens, tools, duration, outcome
- Tool sanitization strips known injection patterns

### Risks
- create_react_agent() API specifics -> consult LangGraph docs, spike test first
- MCP server protocol complexity -> start with subprocess-based MCP, wrap as BaseTool

---

## Phase 2: Memory Layer (Hot/Warm/Cold + RAG)

**Goal:** Three-tier memory system with RAG pipeline. Agents can retrieve project memory, query knowledge graph, get RAG-augmented context.

**Complexity:** XL | **Duration:** ~3 weeks | **Depends on:** Phases 0, 1 | **Parallel with:** Phase 3

### Requirements (13)
| Priority | IDs |
|----------|-----|
| MUST (10) | FR-MEM-001 (Mem0 memory), FR-MEM-002 (Graphiti knowledge graph), FR-MEM-003 (memory scoping), FR-MEM-004 (budget enforcement), FR-MEM-005 (auto-compaction at 70%), FR-MEM-007 (RAG pipeline), FR-MEM-009 (conflict resolution), FR-MEM-010 (conversation history), FR-MEM-011 (write quality gates), FR-MEM-013 (RAG evaluation) |
| SHOULD (3) | FR-MEM-006 (dependency-aware retrieval), FR-MEM-008 (temporal queries), FR-MEM-012 (memory decay) |

### Key Deliverables
1. **Mem0 integration** (`src/colette/memory/project_memory.py`) -- store/retrieve/update/delete scoped by project_id
2. **Knowledge graph** (`src/colette/memory/knowledge_graph.py`) -- Graphiti wrapper, entity/relationship CRUD, bi-temporal queries
3. **RAG pipeline** (`src/colette/memory/rag/`) -- chunker (512 tokens), indexer (pgvector), retriever (BM25 + dense + RRF), reranker (Cohere top-50->top-5), evaluator (RAG Triad)
4. **Context management** (`src/colette/memory/context/`) -- budget tracker, compactor (Morph at 70%), history manager (10 recent + compressed)
5. **Memory write pipeline** (`src/colette/memory/write_pipeline.py`) -- extract -> compare -> CRUD with contradiction detection

### Verification
- Memory persists across sessions, scoped by project_id
- Scoping blocks cross-scope access
- RAG returns relevant results; retrieval p95 <500ms
- Compaction achieves 50-70% reduction at 70% trigger
- Contradictory writes flagged for human resolution
- RAG Triad faithfulness <0.85 triggers alert

### Risks
- Mem0 (0.1.x) instability -> wrap behind interface, swap if needed
- Graphiti/Neo4j complexity -> make optional via feature flag, degrade to vector-only RAG
- Cohere Rerank cost -> implement self-hosted ColBERTv2 fallback

---

## Phase 3: Pipeline Orchestration (StateGraph + Quality Gates + HIL)

**Goal:** LangGraph pipeline connecting 6 stages with quality gates, human-in-the-loop, checkpointing. Stages are stubs but flow control works end-to-end.

**Complexity:** XL | **Duration:** ~2-3 weeks | **Depends on:** Phases 0, 1 | **Parallel with:** Phase 2

### Requirements (20+)
| Priority | IDs |
|----------|-----|
| MUST (13) | FR-ORC-001 (sequential stages), FR-ORC-002 (parallel within stages), FR-ORC-003 (pause/resume), FR-ORC-006 (multi-project), FR-ORC-007 (progress tracking), FR-HIL-001 (approval tiers), FR-HIL-002 (confidence scoring), FR-HIL-003 (review packages), FR-HIL-005 (notifications), all 6 quality gates from Section 12, NFR-REL-006 (checkpoint recovery) |
| SHOULD (5) | FR-ORC-004 (rollback), FR-ORC-005 (stage skip), FR-HIL-004 (feedback learning), FR-HIL-006 (SLA tracking), FR-HIL-008 (inline modification) |
| COULD (2) | FR-ORC-008 (configurable stages), FR-HIL-007 (batch review) |

### Key Deliverables
1. **Pipeline state** (`src/colette/orchestrator/state.py`) -- PipelineState TypedDict
2. **Pipeline graph** (`src/colette/orchestrator/pipeline.py`) -- `build_pipeline()` factory, sequential edges, conditional quality gate edges, checkpointer config
3. **Quality gates** (`src/colette/gates/`) -- `base.py` (protocol), 6 gate implementations (requirements_to_design, design_to_implementation, etc.)
4. **Human-in-the-loop** (`src/colette/human/`) -- `approval.py` (interrupt/resume), `confidence.py`, `notifications.py`, `sla.py`
5. **Progress streaming** (`src/colette/orchestrator/progress.py`) -- stream_mode="updates"
6. **Stage stubs** (`src/colette/stages/*/stage.py`) -- dummy handoffs for testing pipeline flow

### Verification
- Pipeline executes 6 stages in strict sequence
- Quality gate failure blocks progression
- Human approval gates pause and resume correctly
- Confidence <0.60 triggers immediate escalation
- Pipeline survives process death and resumes from checkpoint
- 5 concurrent pipelines run without cross-contamination
- Progress events stream within 2 seconds

### Risks
- interrupt()/Command(resume=) wiring complexity -> dedicated integration test
- Conditional edge complexity -> keep gates as simple boolean evaluators

---

## Phase 4: Requirements + Design Stages (First Real Agents)

**Goal:** First two stages produce real output: NL input -> validated PRD -> system design (OpenAPI, DB schema, UI specs, ADRs).

**Complexity:** XL | **Duration:** ~3 weeks | **Depends on:** Phases 0-3

### Requirements (15)
| Priority | IDs |
|----------|-----|
| MUST (12) | FR-REQ-001 (NL input), FR-REQ-002 (clarification), FR-REQ-003 (PRD generation), FR-REQ-006 (completeness scoring), FR-REQ-007 (traceability), FR-DES-001 (architecture), FR-DES-002 (OpenAPI 3.1), FR-DES-003 (DB schema), FR-DES-004 (UI specs), FR-DES-005 (ADRs), FR-DES-007 (security design), FR-DES-008 (OpenAPI validation) |
| SHOULD (3) | FR-REQ-004 (domain research), FR-REQ-005 (tech recommendation), FR-DES-006 (task decomposition) |

### Key Deliverables
1. **Requirements agents** (`src/colette/stages/requirements/`) -- analyst.py, researcher.py, supervisor.py, prompts.py, tools.py
2. **Design agents** (`src/colette/stages/design/`) -- architect.py, api_designer.py, ui_designer.py, supervisor.py, prompts.py, tools.py
3. **Stage-specific tools** -- web_search.py, openapi_validator.py

### Verification
- NL input produces structured PRD with all required sections
- Completeness score computed; <0.85 blocks gate
- User story IDs follow US-{STAGE}-{NNN} format
- OpenAPI 3.1 spec validates with zero errors
- DB schema normalized to 3NF
- ADRs follow standard format

---

## Phase 5: Implementation Stage (Code Generation)

**Goal:** Three code generation agents (Frontend, Backend, DB) run in parallel, producing linted, type-checked, Git-committed code.

**Complexity:** XL | **Duration:** ~3 weeks | **Depends on:** Phases 0-4

### Requirements (12)
| Priority | IDs |
|----------|-----|
| MUST (10) | FR-IMP-001 through FR-IMP-009, FR-IMP-012 |
| SHOULD (2) | FR-IMP-010 (parallel dev), FR-IMP-011 (inter-agent review) |

### Key Deliverables
1. **Implementation agents** (`src/colette/stages/implementation/`) -- frontend.py, backend.py, database.py, supervisor.py (fan-out via Send)
2. **Code quality enforcement** -- linting, type checking, formatting before PR
3. **Additional tools** -- npm.py, linter.py, type_checker.py, dependency_audit.py

### Verification
- Three agents run in parallel; generated code passes lint + type check with zero errors
- Git workflow: feature branches, meaningful commits, PRs
- OpenAPI contract adherence validated; dependencies pinned with CVE audit

---

## Phase 6: Testing + Deployment Stages

**Goal:** Testing (unit, integration, security scan) and Deployment (Docker, CI/CD, staging auto-deploy, production gate).

**Complexity:** XL | **Duration:** ~3 weeks | **Depends on:** Phases 0-5

### Requirements (19)
| Priority | IDs |
|----------|-----|
| MUST (14) | FR-TST-001 through FR-TST-004, FR-TST-006 through FR-TST-008, FR-DEP-001 through FR-DEP-003, FR-DEP-005, FR-DEP-006, FR-DEP-008, FR-DEP-009 |
| SHOULD (5) | FR-TST-005 (E2E Playwright), FR-TST-010 (a11y), FR-DEP-004 (K8s), FR-DEP-007 (canary), FR-DEP-010 (TLS) |

### Key Deliverables
1. **Testing agents** (`src/colette/stages/testing/`) -- unit_tester, integration_tester, security_scanner, supervisor
2. **Deployment agents** (`src/colette/stages/deployment/`) -- cicd_engineer, infra_engineer, supervisor
3. **Sandboxed execution** (`src/colette/tools/sandbox.py`) -- ephemeral containers with resource limits
4. **Additional tools** -- docker.py, test_runner.py, sast.py, secrets_manager.py

### Verification
- Tests achieve >=80% line, >=70% branch coverage
- Security scan detects injected vulnerabilities; HIGH/CRIT blocks deployment
- Docker containers build and start; CI/CD config valid
- Staging deploys automatically; production requires human approval
- Rollback triggers on health check failure

---

## Phase 7: Monitoring + Security Hardening + Observability

**Goal:** Complete the 6th stage (Monitoring), full security architecture (NFR-SEC-*), production observability (NFR-OBS-*).

**Complexity:** L | **Duration:** ~2 weeks | **Depends on:** Phases 0-6

### Requirements (24)
| Priority | IDs |
|----------|-----|
| MUST (21) | FR-MON-001 through FR-MON-005, NFR-SEC-001 through NFR-SEC-011, NFR-OBS-001 through NFR-OBS-004, NFR-OBS-006 |
| SHOULD (3) | FR-MON-006 (runbooks), FR-MON-008 (SLOs), NFR-OBS-005 (regression alerts) |

### Key Deliverables
1. **Monitoring agents** (`src/colette/stages/monitoring/`) -- observability.py, incident_response.py, supervisor
2. **Security module** (`src/colette/security/`) -- prompt_injection.py, rbac.py, audit.py, mcp_pinning.py, secret_filter.py
3. **Observability finalization** -- dashboards.py, cost_tracker.py, alerts.py

### Verification
- Full 6-stage pipeline end-to-end
- Prompt injection success <10%; secrets never leak; RBAC enforces 4 roles
- Audit log append-only; MCP servers pinned with integrity checks
- OTel traces hierarchical; token/cost tracking aggregated

---

## Phase 8: REST API + CLI + Web UI + Production Readiness

**Goal:** External interfaces and performance hardening. Feature-complete for v1.0.

**Complexity:** L | **Duration:** ~2-3 weeks | **Depends on:** Phases 0-7

### Requirements (21+)
| Priority | IDs |
|----------|-----|
| MUST (17) | NFR-USA-001 (web UI), NFR-USA-002 (REST API), NFR-USA-004 (real-time), NFR-USA-005 (download), NFR-PER-001 through NFR-PER-008, NFR-SCA-001, NFR-SCA-002, NFR-SCA-004, NFR-REL-001 through NFR-REL-005, NFR-REL-008 |
| SHOULD (4) | NFR-USA-003 (CLI), NFR-SCA-003 (10M embeddings), NFR-PER-004, NFR-PER-005 |

### Key Deliverables
1. **REST API** (`src/colette/api/`) -- FastAPI app, routes (projects, pipelines, approvals, artifacts, health, admin), RBAC middleware, WebSocket/SSE
2. **CLI extension** -- submit, status, approve, download commands
3. **Web UI** -- minimal server-rendered (Jinja2 + HTMX) for v1.0; full React is v1.5
4. **Database layer** (`src/colette/db/`) -- SQLAlchemy models, async sessions, Alembic migrations
5. **Performance tuning** -- connection pooling, prompt caching, load testing 5 concurrent pipelines

### Verification
- REST API + OpenAPI 3.1 docs; WebSocket delivers updates within 2 seconds
- CLI submits, monitors, approves, downloads
- RBAC on all endpoints; 5 concurrent pipelines complete
- All NFR-PER latency targets met

---

## Requirements Coverage

| Phase | MUST | SHOULD | COULD | Total |
|-------|------|--------|-------|-------|
| 0: Foundation | 8 | 2 | 0 | 10 |
| 1: Agent Framework | 11 | 1 | 0 | 12 |
| 2: Memory | 10 | 3 | 0 | 13 |
| 3: Pipeline + Gates + HIL | 13 | 5 | 2 | 20 |
| 4: Requirements + Design | 12 | 3 | 2 | 17 |
| 5: Implementation | 10 | 2 | 0 | 12 |
| 6: Testing + Deployment | 14 | 5 | 1 | 20 |
| 7: Monitoring + Security | 21 | 3 | 1 | 25 |
| 8: API + CLI + UI | 17 | 4 | 0 | 21 |
| **Total** | **116** | **28** | **6** | **150** |

Coverage: 116/116 MUST (100%), 28/29 SHOULD (97%), 6/7 COULD (86%)

---

## Team Allocation (if >1 person)

| Engineer | Phases |
|----------|--------|
| A | 0, 1, 3 (foundations, agent framework, pipeline) |
| B | 2 (memory/RAG -- parallel with Phase 3) |
| Both | 4-8 (stage implementations, alternate roles) |

Single engineer: execute strictly 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8.

---

## Global Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| LLM output non-determinism | HIGH | Structured output enforcement, retry loops, validation gates |
| Mem0/Graphiti library instability | MEDIUM | Wrap behind interfaces; feature flags for degradation |
| LangGraph API breaking changes (0.x) | MEDIUM | Pin versions; integration tests catch breakage early |
| Token costs escalate | MEDIUM | Budget enforcement, cost alerts, prompt caching, model tiering |
| 164 requirements is ambitious | HIGH | Strict phase ordering; demo each phase; cut SHOULD/COULD if needed |
| Security testing cannot be exhaustive | HIGH | Published attack datasets; measurable thresholds; defense in depth |
