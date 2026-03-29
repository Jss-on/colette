**SYSTEM ARCHITECTURE**
**Multi-Agent End-to-End**
**Software Development System**
Requirements  →  Design  →  Code  →  Test  →  Deploy  →  Monitor

Cloud-Agnostic  ·  Open Source First  ·  Hybrid Human Oversight
Web Applications: Frontend + Backend + APIs

*Architecture Document v1.0  —  March 2026*

# Table of Contents

# 1. Executive Overview

## 1.1 System Purpose

This architecture defines a multi-agent AI system that autonomously handles the complete software development lifecycle for web applications — from natural language requirements through production deployment and monitoring. The system uses a hybrid oversight model: routine tasks execute autonomously while critical decisions (architecture, security, deployment to production) require human approval.

## 1.2 Design Principles Applied

This architecture applies all ten foundational principles from our research, with three receiving special emphasis for an SDLC system:

- **Structured topologies over unstructured swarms: **The system uses a hierarchical supervisor pattern with sequential pipeline stages, not a free-form agent chat
- **Context quality over quantity: **Each agent receives only domain-relevant context. Code agents never see deployment configs; infra agents never see UI mockups
- **Handoffs are APIs: **Every inter-agent transfer uses typed Pydantic schemas with versioned contracts. No free-text handoffs between pipeline stages

## 1.3 Key Architecture Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Orchestration framework | LangGraph | Best token efficiency, graph-based state, durable execution with failure recovery, production-proven at 400+ companies |
| Orchestration pattern | Hierarchical supervisor + sequential pipeline | +80.8% on parallelizable tasks (Google/MIT); sequential pipeline for progressive refinement across SDLC stages |
| Memory system | Mem0 (user/project) + Graphiti (codebase knowledge) + LangGraph shared state (session) | Hybrid vector+graph for codebase understanding; Mem0 for cross-session project memory |
| RAG pipeline | Recursive chunking + pgvector + Cohere Rerank | 69% accuracy benchmark default; +33-40% from reranking; pgvector for unified stack |
| Tool integration | MCP (Model Context Protocol) | 97M monthly SDK downloads; Linux Foundation governance; 10,000+ public servers |
| Context management | Morph Compact + 70% trigger | 98% verbatim accuracy; 50-70% compression; avoids summarization hallucination |
| Human oversight | Confidence-gated hybrid | Autonomous below threshold; human approval for architecture, security, prod deploys |
| Source control | Git-native (every artifact versioned) | Full audit trail; rollback capability; PR-based review gates |

# 2. High-Level System Architecture

## 2.1 Three-Layer Design

The system is organized into three distinct layers, each independently scalable and observable.

**Layer 1: Orchestration Layer (LangGraph)**
The orchestration layer manages the SDLC pipeline as a directed acyclic graph. A Project Orchestrator agent sits at the top, decomposing user requests into pipeline stages and delegating to Stage Supervisors. Each stage supervisor manages 2–4 specialist agents.

| PIPELINE FLOW User Request → Project Orchestrator → Requirements Stage → Design Stage → Implementation Stage → Testing Stage → Deployment Stage → Monitoring Stage → Delivery to User |
| --- |

**Layer 2: Memory Layer (Hybrid)**

- **Project Memory (Mem0): **Cross-session persistence of project context, user preferences, architectural decisions, domain-specific patterns. Scoped by project_id + user_id
- **Codebase Knowledge Graph (Graphiti): **Temporal knowledge graph of code entities, dependencies, API contracts, schema evolution. Bi-temporal tracking for understanding how the codebase evolved
- **Session State (LangGraph Checkpoints): **Within-session state for the current pipeline execution. TypedDict schemas with reducer-based merging. Auto-persisted at every super-step

**Layer 3: Context Management Layer**

- **Token Budget Controller: **Enforces per-agent context budgets. System prompt 15% | Tools 15% | Retrieved context 35% | History 15% | Output+reasoning 20%
- **Context Compactor: **Morph Compact triggers at 70% utilization. Verbatim compaction (no summarization) preserves exact code snippets and error messages
- **RAG Pipeline: **Chunked codebase + documentation indexed in pgvector. Hybrid retrieval (BM25 + dense) with Cohere Rerank. Position-aware injection

## 2.2 Pipeline Stage Architecture

The SDLC pipeline consists of six sequential stages, each with a stage supervisor and specialist agents. Between stages, structured handoff objects transfer only relevant artifacts and decisions.

| Stage | Supervisor | Specialist Agents | Outputs | Human Gate |
| --- | --- | --- | --- | --- |
| 1. Requirements | Requirements Supervisor | Analyst, Researcher | PRD, user stories, acceptance criteria | Approve PRD |
| 2. Design | Design Supervisor | Architect, API Designer, UI/UX Designer | System design doc, API specs, wireframes, DB schema | Approve architecture |
| 3. Implementation | Implementation Supervisor | Frontend Dev, Backend Dev, DB Engineer | Source code, migrations, configs | Review PRs for critical changes |
| 4. Testing | Testing Supervisor | Unit Tester, Integration Tester, Security Scanner | Test suites, coverage reports, vulnerability scan | Approve if security issues found |
| 5. Deployment | Deployment Supervisor | CI/CD Engineer, Infra Engineer | Docker configs, CI/CD pipeline, IaC manifests | Approve production deploy |
| 6. Monitoring | Monitoring Supervisor | Observability Agent, Incident Agent | Dashboards, alerts, runbooks, incident reports | Escalate critical incidents |

# 3. Complete Agent Catalog

## 3.1 Project Orchestrator (Top-Level Supervisor)

| Project Orchestrator Role: Top-level supervisor. Receives user requests, decomposes into SDLC stages, routes to stage supervisors, monitors progress, synthesizes final delivery. Maintains the Project Ledger (facts, decisions, blockers) and Progress Ledger (stage completion, quality gates). Tools: stage_router, project_memory_read, project_memory_write, human_escalation, progress_tracker (5 tools) Model: Claude Opus 4.6 (frontier model for planning; cheaper models execute) Approval: Autonomous for routing; Human approval for scope changes |
| --- |

## 3.2 Stage 1: Requirements Agents

| Requirements Supervisor Role: Manages requirements elicitation. Coordinates Analyst and Researcher agents. Produces final PRD with user stories, acceptance criteria, and technical constraints. Tools: analyst_delegate, researcher_delegate, prd_template, acceptance_criteria_gen (4 tools) Model: Claude Sonnet 4.6 Approval: Human approval required for final PRD |
| --- |

| Requirements Analyst Role: Extracts functional and non-functional requirements from user input. Identifies ambiguities, asks clarifying questions, decomposes features into user stories with acceptance criteria. Tools: clarification_prompt, user_story_writer, constraint_extractor (3 tools) Model: Claude Sonnet 4.6 Approval: Autonomous |
| --- |

| Domain Researcher Role: Researches domain context, existing solutions, API documentation, and technical feasibility. Provides competitive analysis and technology recommendations. Tools: web_search, doc_fetcher, api_explorer, tech_stack_advisor (4 tools) Model: Claude Sonnet 4.6 Approval: Autonomous |
| --- |

## 3.3 Stage 2: Design Agents

| Design Supervisor Role: Coordinates architecture, API, and UI design. Ensures consistency across design artifacts. Produces unified system design document. Tools: architect_delegate, api_designer_delegate, ui_designer_delegate, design_validator (4 tools) Model: Claude Opus 4.6 (architecture decisions require frontier reasoning) Approval: Human approval required for architecture decisions |
| --- |

| System Architect Role: Designs system architecture: component decomposition, technology selection, data flow, scalability patterns, security model. Produces architecture decision records (ADRs). Tools: architecture_template, pattern_library, tech_evaluator, adr_writer (4 tools) Model: Claude Opus 4.6 Approval: Human approval for all ADRs |
| --- |

| API Designer Role: Designs RESTful/GraphQL APIs. Produces OpenAPI 3.1 specifications with request/response schemas, authentication flows, rate limiting, and versioning strategy. Tools: openapi_generator, schema_validator, api_linter, contract_tester (4 tools) Model: Claude Sonnet 4.6 Approval: Autonomous (validated by schema tools) |
| --- |

| UI/UX Designer Role: Creates component hierarchies, page layouts, navigation flows, and design system specifications. Produces wireframe descriptions and component specs in structured format. Tools: component_library, layout_generator, accessibility_checker, design_system_ref (4 tools) Model: Claude Sonnet 4.6 Approval: Autonomous |
| --- |

## 3.4 Stage 3: Implementation Agents

| Implementation Supervisor Role: Coordinates frontend, backend, and database implementation. Manages code review between agents. Ensures all code passes linting, type checking, and basic tests before handoff. Tools: frontend_delegate, backend_delegate, db_delegate, code_review_orchestrator, git_manager (5 tools) Model: Claude Sonnet 4.6 Approval: Human review for PRs touching auth, payments, or data models |
| --- |

| Frontend Developer Role: Implements React/Next.js frontend components, pages, state management, API integration, and responsive layouts. Follows design system specifications from UI/UX Designer. Tools: file_writer, npm_runner, eslint, typescript_compiler, component_scaffold (5 tools) Model: Claude Sonnet 4.6 Approval: Autonomous for routine; Human review for complex state logic |
| --- |

| Backend Developer Role: Implements API endpoints, business logic, authentication, authorization, data validation, and third-party integrations. Follows OpenAPI specs from API Designer. Tools: file_writer, package_manager, linter, type_checker, api_test_runner (5 tools) Model: Claude Sonnet 4.6 Approval: Autonomous for CRUD; Human review for auth/security logic |
| --- |

| Database Engineer Role: Designs and implements database schemas, migrations, indexes, and seed data. Handles ORM configuration, query optimization, and data integrity constraints. Tools: migration_generator, schema_validator, query_analyzer, seed_generator (4 tools) Model: Claude Sonnet 4.6 Approval: Human approval for production migration scripts |
| --- |

## 3.5 Stage 4: Testing Agents

| Testing Supervisor Role: Coordinates test generation, execution, and reporting. Enforces coverage thresholds (80% line, 70% branch). Gates handoff to deployment on test pass rates. Tools: unit_tester_delegate, integration_tester_delegate, security_scanner_delegate, coverage_reporter (4 tools) Model: Claude Sonnet 4.6 Approval: Human approval if coverage below threshold or security issues found |
| --- |

| Unit Test Engineer Role: Generates comprehensive unit tests for all modules. Uses property-based testing for edge cases. Targets 80%+ line coverage with meaningful assertions, not just coverage padding. Tools: test_writer, test_runner, coverage_analyzer, mock_generator (4 tools) Model: Claude Sonnet 4.6 Approval: Autonomous |
| --- |

| Integration Test Engineer Role: Creates API integration tests, E2E browser tests, and contract tests. Validates API responses against OpenAPI specs. Tests authentication flows and error handling. Tools: api_test_writer, e2e_test_writer, contract_validator, test_runner (4 tools) Model: Claude Sonnet 4.6 Approval: Autonomous |
| --- |

| Security Scanner Role: Runs SAST (static analysis), dependency vulnerability scanning, secrets detection, and OWASP Top 10 checks. Produces severity-ranked vulnerability report. Tools: sast_runner, dependency_audit, secrets_scanner, owasp_checker (4 tools) Model: Claude Sonnet 4.6 Approval: Human escalation for HIGH/CRITICAL findings |
| --- |

## 3.6 Stage 5: Deployment Agents

| Deployment Supervisor Role: Coordinates CI/CD pipeline creation and infrastructure provisioning. Manages staging vs. production deployment decisions. Implements blue-green or canary deployment strategies. Tools: cicd_delegate, infra_delegate, deploy_gate, rollback_manager (4 tools) Model: Claude Sonnet 4.6 Approval: Human approval required for ALL production deployments |
| --- |

| CI/CD Engineer Role: Creates GitHub Actions / GitLab CI pipelines. Configures build, test, lint, security scan, and deploy stages. Implements automated rollback on health check failure. Tools: pipeline_generator, workflow_validator, artifact_builder, registry_manager (4 tools) Model: Claude Sonnet 4.6 Approval: Autonomous for staging; Human approval for production pipeline changes |
| --- |

| Infrastructure Engineer Role: Generates Docker/Docker Compose configurations, Kubernetes manifests, and optional Terraform IaC. Configures networking, secrets management, and resource limits. Tools: dockerfile_generator, k8s_manifest_writer, terraform_writer, secrets_manager (4 tools) Model: Claude Sonnet 4.6 Approval: Human approval for infrastructure changes |
| --- |

## 3.7 Stage 6: Monitoring Agents

| Monitoring Supervisor Role: Sets up observability stack and manages incident response. Creates dashboards, alerts, and runbooks. Monitors deployed application health. Tools: observability_delegate, incident_delegate, health_checker, alert_manager (4 tools) Model: Claude Sonnet 4.6 Approval: Human escalation for P0/P1 incidents |
| --- |

| Observability Agent Role: Configures logging (structured JSON), metrics (Prometheus/Grafana), tracing (OpenTelemetry), and error tracking (Sentry). Creates SLO definitions and dashboard templates. Tools: logging_config, metrics_setup, tracing_setup, dashboard_generator (4 tools) Model: Claude Sonnet 4.6 Approval: Autonomous |
| --- |

| Incident Response Agent Role: Monitors health endpoints, analyzes error patterns, generates root cause hypotheses, and creates runbooks. Can trigger automated rollback for failing deployments. Tools: health_monitor, log_analyzer, rca_generator, runbook_writer, rollback_trigger (5 tools) Model: Claude Sonnet 4.6 Approval: Autonomous for rollback; Human escalation for data-affecting incidents |
| --- |

# 4. Inter-Stage Handoff Contracts

Every stage-to-stage transition uses a typed Pydantic schema. This is the single most important reliability mechanism — free-text handoffs are the primary source of context loss in production multi-agent systems (GuruSup measured 60–70% token reduction using structured handoffs).

## 4.1 Handoff Schema Design Principles

- **Carry forward: **User identity, project_id, key decisions, entity references, error context, quality gate results
- **Summarize: **Intermediate reasoning chains, exploration paths that were abandoned
- **Drop: **Verbose tool call logs, social niceties, duplicate information, raw LLM outputs
- **Version: **Every schema has a version field. Breaking changes increment major version. Agents validate schema version on receipt

## 4.2 Stage Handoff Schemas

**Requirements → Design Handoff**

| Field | Type | Description |
| --- | --- | --- |
| project_id | str | Unique project identifier |
| prd_version | str | Semantic version of the PRD |
| functional_requirements | List[UserStory] | User stories with acceptance criteria |
| non_functional_requirements | NFRSpec | Performance, security, scalability constraints |
| tech_constraints | List[str] | Mandated technologies, integrations, compatibility requirements |
| domain_context | str | Compressed domain knowledge (max 2000 tokens) |
| approval_status | ApprovalRecord | Human approval timestamp, approver, comments |
| open_questions | List[Question] | Unresolved ambiguities flagged for Design stage |

**Design → Implementation Handoff**

| Field | Type | Description |
| --- | --- | --- |
| architecture_doc | ArchitectureSpec | Component diagram, data flow, technology stack, ADRs |
| api_specs | List[OpenAPISpec] | OpenAPI 3.1 specifications for all endpoints |
| db_schema | DatabaseSchema | Entity-relationship model, migration plan, index strategy |
| ui_specs | List[ComponentSpec] | Component hierarchy, props interfaces, page layouts |
| design_decisions | List[ADR] | Architecture Decision Records with rationale |
| implementation_plan | TaskGraph | DAG of implementation tasks with dependencies and priorities |
| quality_gates | QualityConfig | Coverage thresholds, linting rules, type-checking config |

**Implementation → Testing Handoff**

| Field | Type | Description |
| --- | --- | --- |
| git_ref | str | Git commit SHA of the implementation |
| changed_files | List[FileDiff] | Files created/modified with diff summaries |
| api_endpoints | List[EndpointMeta] | Implemented endpoints with route, method, auth requirements |
| db_migrations | List[Migration] | Migration files with up/down operations |
| env_config | EnvSpec | Required environment variables, services, ports |
| known_limitations | List[str] | Known gaps, TODOs, or temporary workarounds |
| test_hints | List[TestHint] | Suggested test scenarios from implementation context |

**Testing → Deployment Handoff**

| Field | Type | Description |
| --- | --- | --- |
| test_results | TestReport | Pass/fail counts, coverage percentages, timing |
| security_report | SecurityReport | Vulnerability findings ranked by severity |
| api_contract_status | ContractReport | API contract test results vs. OpenAPI specs |
| deploy_readiness | ReadinessScore | Composite score (0-100) based on test/security/coverage gates |
| blocking_issues | List[Issue] | Issues that must be resolved before deployment |
| advisory_issues | List[Issue] | Non-blocking recommendations |

**Deployment → Monitoring Handoff**

| Field | Type | Description |
| --- | --- | --- |
| deployment_id | str | Unique deployment identifier |
| environment | str | staging | production |
| service_endpoints | List[Endpoint] | Deployed URLs with health check paths |
| resource_config | ResourceSpec | CPU/memory limits, replica count, auto-scaling rules |
| deploy_strategy | str | blue-green | canary | rolling |
| rollback_config | RollbackSpec | Automated rollback conditions and procedures |
| slo_targets | List[SLO] | Latency p99, error rate, availability targets |

# 5. Memory Architecture

## 5.1 Three-Tier Memory System

| Tier | Technology | Scope | Latency | Persistence |
| --- | --- | --- | --- | --- |
| Hot (Working) | LangGraph context window | Current agent turn | <1ms | Session only |
| Warm (Active) | Mem0 + Graphiti + pgvector | Cross-session project knowledge | <100ms | Persistent |
| Cold (Archive) | Object storage (S3-compatible) | Historical project snapshots, old PRDs | On-demand | Persistent |

## 5.2 Codebase Knowledge Graph (Graphiti)

The codebase knowledge graph is the most critical memory component for an SDLC system. It stores structured understanding of the code being developed, enabling agents to reason about dependencies, impacts, and evolution.

- **Entity nodes: **Files, functions, classes, API endpoints, database tables, environment variables, npm packages
- **Relationship edges: **imports, calls, extends, implements, depends_on, reads_from, writes_to, tested_by
- **Temporal tracking: **Bi-temporal model tracks when code entities were created, modified, and deleted — enabling queries like “what changed since the last deploy?”
- **Community detection: **Leiden algorithm identifies module boundaries and coupling patterns for architectural recommendations

## 5.3 Project Memory (Mem0)

Project memory persists across sessions and stores high-level project context that any agent might need.

- **Architectural decisions: **ADRs, technology choices, design rationale
- **User preferences: **Coding style, framework preferences, naming conventions
- **Domain knowledge: **Business rules, regulatory requirements, integration constraints
- **Lessons learned: **Past failures, successful patterns, performance optimizations discovered
- **Scoping: **project_id + user_id + agent_id metadata filtering. Agents only retrieve memories relevant to their scope

## 5.4 Memory Scoping Rules

| Memory Type | Scope | Access Pattern |
| --- | --- | --- |
| User preferences | Global (across projects) | Read by all agents, written by Orchestrator |
| Project requirements | Project-scoped | Read by all project agents, written by Requirements stage |
| Architecture decisions | Project-scoped | Read by Implementation+, written by Design stage |
| Code entity relationships | Project-scoped | Read/written by Implementation + Testing agents |
| Deployment configs | Project + environment | Read/written by Deployment + Monitoring agents |
| Incident history | Project + environment | Read by all agents, written by Monitoring stage |
| Agent reasoning chains | Agent-private | Never shared — private scratchpad only |

# 6. Human-in-the-Loop Architecture

## 6.1 Approval Gate Classification

Every agent action is classified into one of four tiers based on blast radius and reversibility.

| Tier | Approval | SLA | Examples |
| --- | --- | --- | --- |
| T0: Critical | Human required | 1 hour | Production deployments, database migrations, security architecture, auth flows |
| T1: High | Human review | 4 hours | API contract changes, new dependencies, infrastructure changes, PR merges to main |
| T2: Moderate | Confidence-gated | Async audit | Code generation, test writing, documentation, CI/CD config for staging |
| T3: Routine | Fully autonomous | N/A | Linting, formatting, unit test execution, log analysis, health checks |

## 6.2 Confidence-Gated Approval Flow

For T2 (moderate) actions, agents output a confidence score (0.0–1.0) with each decision. The system routes based on thresholds:

- **Confidence ≥ 0.85: **Proceed autonomously. Log for async audit (batch reviewed weekly)
- **Confidence 0.60–0.85: **Proceed with flag. Highlighted in next human review cycle (daily)
- **Confidence < 0.60: **Escalate immediately. Agent pauses and presents options to human reviewer

| TARGET ESCALATION RATE Aim for 10–15% of T2 actions escalating to human review. Below 5% suggests thresholds are too permissive; above 25% suggests agents need better context or tooling. |
| --- |

## 6.3 Human Review Interface

The system presents human reviewers with structured decision packages, not raw agent outputs.

- **Context summary: **What was the agent trying to do and why (2–3 sentences)
- **Proposed action: **Exactly what the agent wants to do (diff, config change, deployment target)
- **Risk assessment: **What could go wrong, blast radius, reversibility
- **Alternatives considered: **Other options the agent evaluated and why they were rejected
- **Action buttons: **Approve / Reject / Modify / Request More Info
- **Feedback loop: **Every human decision is stored in project memory to improve future agent confidence calibration

# 7. Tool & MCP Integration Map

## 7.1 MCP Server Architecture

All external tool integrations use Model Context Protocol (MCP) servers, providing a unified interface and avoiding vendor lock-in. Each MCP server exposes a well-defined set of tools with JSON Schema parameter definitions.

| MCP Server | Tools Exposed | Used By |
| --- | --- | --- |
| mcp-git | clone, branch, commit, push, pull, diff, merge, pr_create, pr_review | Implementation, Testing, Deployment supervisors |
| mcp-filesystem | read_file, write_file, list_dir, search_files, move_file | All Implementation agents |
| mcp-terminal | run_command, run_script (sandboxed) | Testing, Deployment, Monitoring agents |
| mcp-browser | fetch_url, screenshot, dom_query | Researcher, Integration Tester |
| mcp-database | query, migrate, schema_inspect, seed | DB Engineer, Testing agents |
| mcp-docker | build, run, stop, logs, compose_up | CI/CD Engineer, Infra Engineer |
| mcp-kubernetes | apply, get, describe, rollout, scale | Infra Engineer, Monitoring agents |
| mcp-secrets | get_secret, set_secret, rotate_secret | Deployment agents only (restricted) |
| mcp-monitoring | query_metrics, create_alert, get_logs, create_dashboard | Monitoring agents |
| mcp-search | web_search, doc_search, code_search | Researcher, all agents (read-only) |

## 7.2 Tool Access Control

Tools follow the principle of least privilege. Each agent is granted access only to the MCP servers required for its role. High-risk tools (secrets, production k8s, database migrations) require additional authentication and audit logging.

| SECURITY BOUNDARY MCP tool poisoning is an active attack vector. All MCP server descriptions are reviewed and pinned to specific versions. Agents never install MCP servers from untrusted sources. Tool outputs from untrusted external systems (web search, user-provided APIs) are processed by quarantined LLM instances that cannot trigger consequential actions. |
| --- |

# 8. Context Management Strategy

## 8.1 Per-Agent Context Budget

Each agent operates within a strict context budget. The Implementation Supervisor enforces budgets across its specialist agents to prevent context bloat from accumulating across the stage.

| Agent Category | Max Context | System Prompt | Tools | Retrieved | History | Output |
| --- | --- | --- | --- | --- | --- | --- |
| Supervisors | 100K tokens | 10K (10%) | 15K (15%) | 35K (35%) | 15K (15%) | 25K (25%) |
| Specialist agents | 60K tokens | 6K (10%) | 9K (15%) | 24K (40%) | 9K (15%) | 12K (20%) |
| Scanner/validator | 30K tokens | 3K (10%) | 5K (17%) | 12K (40%) | 5K (17%) | 5K (17%) |

## 8.2 Code-Specific Context Strategies

- **File-level chunking: **Each source file is one chunk (up to 2000 tokens). Files exceeding this are split at function/class boundaries
- **Dependency-aware retrieval: **When retrieving a file, also retrieve its direct imports and the interfaces it implements (1-hop graph traversal from Graphiti)
- **Diff-focused context: **For code review and testing, inject only the diff + 10 lines of surrounding context, not entire files
- **API spec injection: **When coding an endpoint, inject only the relevant OpenAPI path spec, not the full API document
- **Error-context enrichment: **When a build/test fails, inject the error message + the specific file/line referenced + the most recent change to that file

## 8.3 Compaction Triggers

- **Time-based: **Every 15 minutes of continuous agent operation, compact non-essential history
- **Utilization-based: **Trigger at 70% context utilization (primary trigger)
- **Stage-transition: **Full compaction at every stage handoff. Only structured handoff schema crosses the boundary
- **Error-recovery: **After 3 consecutive failures, compact and retry with clean context (concat-and-retry pattern)

| CONCAT-AND-RETRY FOR ERROR RECOVERY When an agent fails repeatedly, consolidate all gathered information into a single clean prompt and send to a fresh LLM instance. This pushes accuracy back above 90% (Microsoft/Salesforce study across 200K simulated conversations). |
| --- |

# 9. Quality Assurance & Evaluation

## 9.1 Quality Gates Per Stage

| Stage Exit Gate | Criteria | Enforcement |
| --- | --- | --- |
| Requirements → Design | PRD completeness score ≥ 0.85; all user stories have acceptance criteria; human-approved | Automated scoring + human gate |
| Design → Implementation | API specs validate against OpenAPI 3.1; DB schema passes normalization check; ADRs approved | Schema validation + human gate |
| Implementation → Testing | Zero linting errors; TypeScript compiles; all endpoints return 200 on smoke test | Automated CI checks |
| Testing → Deployment | 80% line coverage, 70% branch; zero HIGH/CRITICAL vulnerabilities; API contract tests pass | Automated thresholds + human if security issues |
| Deployment → Monitoring | Health checks pass; canary metrics within SLO; no error rate spike | Automated health checks + human for prod |

## 9.2 Agent Performance Metrics

| Metric | Target | Measurement |
| --- | --- | --- |
| Task completion rate | ≥ 90% first attempt | Percentage of agent tasks completed without retry or escalation |
| Handoff fidelity | ≥ 98% | Percentage of handoff schemas passing validation on receipt |
| Context utilization | 30–70% | Average context window utilization across agents |
| Token cost per project | Track and trend | Total tokens consumed per SDLC pipeline execution |
| Hallucination rate | < 5% | Claims not supported by retrieved context or code (sampled audit) |
| Human escalation rate | 10–15% of T2 actions | Percentage of moderate-risk actions requiring human review |
| Cycle time | Track and trend | Total elapsed time from requirement to deployment |
| Rollback rate | < 5% of deployments | Percentage of deployments requiring rollback |

## 9.3 Observability Stack

- **Agent tracing: **LangSmith or Arize Phoenix (OpenTelemetry-native). Hierarchical trace visualization for multi-agent debugging
- **RAG evaluation: **RAGAS faithfulness + context relevance + answer relevance on every retrieval call. Alert if faithfulness drops below 0.85
- **Code quality: **Automated linting (ESLint, Ruff), type checking (TypeScript, mypy), complexity analysis (SonarQube) on every generated file
- **Pipeline metrics: **Custom Grafana dashboard tracking tokens/stage, latency/stage, escalation rate, quality gate pass rates
- **Cost monitoring: **Per-agent token consumption tracking with alerts when any agent exceeds 2× baseline

# 10. Infrastructure & Deployment

## 10.1 System Components

| Component | Technology | Purpose |
| --- | --- | --- |
| Orchestration runtime | LangGraph + Redis (checkpointing) | Stateful agent execution with durable checkpoints |
| Message queue | Redis Streams or NATS | Async communication between stage supervisors |
| Vector database | pgvector (PostgreSQL extension) | Code/doc embeddings for RAG retrieval |
| Knowledge graph | Neo4j (via Graphiti) | Codebase entity-relationship graph |
| Memory service | Mem0 (self-hosted, Apache 2.0) | Project memory with vector + graph backend |
| Git service | Gitea or GitHub (self-hosted option) | Source control for all generated artifacts |
| Container runtime | Docker + Docker Compose | Sandboxed execution for builds, tests, and deploys |
| CI/CD runner | GitHub Actions or Woodpecker CI | Pipeline execution for generated CI/CD configs |
| Monitoring | Prometheus + Grafana + Loki | System and agent metrics, logs, dashboards |
| Tracing | Arize Phoenix (OpenTelemetry) | Multi-agent trace visualization and debugging |
| LLM gateway | LiteLLM (open source) | Unified API for multiple LLM providers with fallback chains |

## 10.2 LLM Provider Strategy

Use LiteLLM as a unified gateway to abstract LLM provider selection. This enables model fallback chains, cost optimization through routing, and provider migration without code changes.

| Role | Primary Model | Fallback | Rationale |
| --- | --- | --- | --- |
| Planning (Orchestrator, Architects) | Claude Opus 4.6 | GPT-5.4 | Frontier reasoning for high-stakes decisions |
| Execution (all specialist agents) | Claude Sonnet 4.6 | GPT-4.1 | Best cost/quality balance for code generation |
| Validation (scanners, linters) | Claude Haiku 4.5 | GPT-4.1-mini | Fast, cheap validation passes |
| Embedding | Voyage 3 Large | text-embedding-3-large | Top MTEB retrieval scores |
| Reranking | Cohere Rerank 4 Pro | ColBERTv2 (self-hosted) | Best reranking quality; self-hosted fallback for cost |

## 10.3 Scaling Considerations

- **Horizontal scaling: **Each stage supervisor + its agents can run as an independent process. Multiple projects execute in parallel via separate LangGraph instances
- **Token cost management: **Prompt caching (Anthropic: 90% savings, OpenAI: 50%) for stable system prompts + tool definitions. Plan-and-Execute pattern: Opus plans, Sonnet/Haiku executes
- **Concurrency: **Within Implementation stage, Frontend Dev, Backend Dev, and DB Engineer run in parallel (fan-out). Results merge at Implementation Supervisor (fan-in)
- **Rate limiting: **LiteLLM handles per-provider rate limits with automatic queuing and retry

# 11. Security Architecture

## 11.1 Threat Model

| Threat | Mitigation |
| --- | --- |
| Prompt injection via user requirements | Dual-LLM architecture: planning LLM (trusted) + data-processing LLM (quarantined). CaMeL-inspired isolation |
| MCP tool poisoning | Pin MCP server versions; review all tool descriptions; sandboxed execution for untrusted tool outputs |
| Memory poisoning | Confidence-gated memory writes; human audit of HIGH importance memories; bi-temporal tracking for rollback |
| Secret exfiltration | mcp-secrets restricted to Deployment agents only; secrets never appear in agent context; KMS-backed storage |
| Malicious code generation | SAST scanning on all generated code; sandbox execution; no direct production access without human approval |
| Supply chain attacks | Dependency audit on every generated package.json/requirements.txt; lock files required; vulnerability scanning |
| Context window manipulation | Strict token budgets per agent; context compaction prevents unbounded growth; structured handoffs prevent context injection |

## 11.2 Sandboxing Model

All code execution (builds, tests, scripts) runs in ephemeral Docker containers with the following constraints:

- No network access except to approved registries (npm, PyPI, Docker Hub)
- Read-only access to project source; write access only to build output directories
- CPU and memory limits (2 CPU, 4GB RAM default; configurable per project)
- Maximum execution time (10 minutes for builds, 30 minutes for full test suites)
- No access to host filesystem, secrets, or other containers

# 12. Getting Started: Phased Rollout

## Phase 1: Core Pipeline (Weeks 1–4)

Deploy the Project Orchestrator + Requirements Stage + Implementation Stage (Backend Dev only). This gives you a working end-to-end flow for simple API generation from natural language requirements.

- Install LangGraph, Mem0, pgvector, LiteLLM, Arize Phoenix
- Configure MCP servers: mcp-git, mcp-filesystem, mcp-terminal
- Define handoff schemas for Requirements → Implementation
- Set up human approval gate for PRD review
- Target: Generate a working REST API from a 1-paragraph description

## Phase 2: Full Stack (Weeks 5–8)

Add Design Stage, Frontend Dev, DB Engineer, and Testing Stage. Enable parallel execution within Implementation stage.

- Add API Designer, System Architect, Frontend Dev, DB Engineer agents
- Deploy Graphiti for codebase knowledge graph
- Add Testing Supervisor with Unit and Integration test agents
- Configure quality gates at each stage transition
- Target: Generate a full-stack web app with tests from a PRD

## Phase 3: DevOps & Monitoring (Weeks 9–12)

Add Deployment and Monitoring stages. Enable CI/CD pipeline generation and automated deployment to staging.

- Add CI/CD Engineer, Infra Engineer, Monitoring agents
- Configure mcp-docker, mcp-kubernetes, mcp-monitoring servers
- Set up human approval gates for production deployments
- Deploy Prometheus + Grafana for system observability
- Target: Full end-to-end from requirements to monitored staging deployment

## Phase 4: Optimization (Ongoing)

- Enable prompt caching for 50–90% cost reduction
- Implement Plan-and-Execute (Opus plans, Haiku validates, Sonnet executes)
- Add Security Scanner agent with SAST and dependency audit
- Train confidence calibration on accumulated human feedback data
- A/B test context management strategies (compaction vs. summarization vs. truncation)
- Target: Reduce cycle time by 50% and cost per project by 70%

## Final Note

This architecture is designed to be **incrementally adoptable**. You don’t need all 18 agents on day one. Start with Phase 1 (3 agents), prove value, and expand. Every component — the orchestration framework, memory tools, MCP servers, LLM providers — is open-source and replaceable. The structured handoff contracts and typed schemas ensure that you can swap any individual component without rebuilding the system.

The architecture embodies the single most important finding from our research: **the teams that invest in context engineering and structured orchestration consistently outperform those that chase the newest model.** Build the architecture right, and any frontier model will deliver reliable results.
