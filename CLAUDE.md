# CLAUDE.md

> **Version:** 3.0 | **Last updated:** 2026-03-29 | **Status:** Scaffolded — dev environment ready

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Colette** is a multi-agent AI system that autonomously performs end-to-end software development for web applications. It handles the full SDLC from natural language requirements through production deployment and monitoring, using a hybrid oversight model where routine tasks execute autonomously while critical decisions require human approval.

**Current status:** Scaffolded. Project structure, build system, CI, and dev tooling are in place. Core implementation has not started.

## Target Tech Stack

- **Language:** Python 3.13+ (managed via `uv`)
- **Orchestration:** LangGraph (graph-based state machine, chosen for token efficiency and durable execution)
- **Memory:** Mem0 (project/user memory) + Graphiti/Zep (codebase knowledge graph with bi-temporal tracking) + LangGraph shared state (session)
- **RAG:** Recursive chunking at 512 tokens + pgvector + Cohere Rerank
- **LLM Gateway:** LiteLLM (open-source, provider-agnostic; Claude, GPT, Gemini via unified API with fallback chains and usage tracking)
- **Tool Integration:** MCP (Model Context Protocol) servers for all external tools
- **Context Compression:** Morph Compact (verbatim, no summarization) triggered at 70% utilization
- **Target apps:** React/Next.js frontend, Node.js or Python backend, PostgreSQL database

## Architecture

### Three-Layer Design

1. **Orchestration Layer (LangGraph):** SDLC pipeline as a DAG. A Project Orchestrator decomposes requests into pipeline stages, delegates to Stage Supervisors, each managing 2-4 specialist agents.
2. **Memory Layer (Hybrid):** Hot (LangGraph context window) → Warm (Mem0 + Graphiti + pgvector) → Cold (S3-compatible archive).
3. **Context Management Layer:** Per-agent token budgets, Morph Compact at 70%, RAG with hybrid retrieval (BM25 + dense vectors + reranking).

### Six-Stage Sequential Pipeline

```
User Request → Requirements → Design → Implementation → Testing → Deployment → Monitoring → Delivery
```

Each stage has a **supervisor** agent and **2-4 specialist agents**. Inter-stage transfers use **typed Pydantic handoff schemas** (versioned, validated). No free-text handoffs.

### Key Agents (16 total)

| Stage | Supervisor | Specialists |
|---|---|---|
| Requirements | Requirements Supervisor | Analyst, Domain Researcher |
| Design | Design Supervisor | System Architect, API Designer, UI/UX Designer |
| Implementation | Implementation Supervisor | Frontend Dev, Backend Dev, DB Engineer |
| Testing | Testing Supervisor | Unit Tester, Integration Tester, Security Scanner |
| Deployment | Deployment Supervisor | CI/CD Engineer, Infra Engineer |
| Monitoring | Monitoring Supervisor | Observability Agent, Incident Response Agent |

**Model assignment:** Opus for planning/architecture (Orchestrator, Design Supervisor, System Architect); Sonnet for execution (all others).

### Human Oversight Tiers

- **T0 (Critical):** Human required — production deploys, DB migrations, security architecture
- **T1 (High):** Human review — API contract changes, new dependencies, infra changes
- **T2 (Moderate):** Confidence-gated — code generation, test writing, staging CI/CD (escalate if confidence < 0.60)
- **T3 (Routine):** Fully autonomous — linting, formatting, test execution, log analysis

### Context Budgets

- Supervisors: 100K tokens (10% system prompt, 15% tools, 35% retrieved context, 15% history, 25% output)
- Specialist agents: 60K tokens (same proportions, 40% retrieved context)
- Scanners/validators: 30K tokens

## Design Constraints

- **Cloud-agnostic:** Must run on AWS, GCP, Azure, or on-premises
- **Open-source first:** Every component must have an OSS option
- **LLM provider agnostic:** All LLM calls go through LiteLLM gateway
- **Data residency:** All project data stays on user infrastructure; no third-party data sharing except LLM API calls
- **Horizontal scalability:** Concurrent project execution with full isolation

## Documentation Reference

All planning documents are in `docs/`. Markdown versions are authoritative; .docx files are retained as archives.

### Primary Documents (Markdown)
- `Colette_Software_Requirements_Specification.md` — 164 requirements across 16 domains (MoSCoW prioritized, IEEE 830 compliant)
- `MultiAgent_SDLC_System_Architecture.md` — Full architecture: agent catalog, handoff schemas, memory tiers, MCP integration, infrastructure
- `Complete_Guide_to_Building_AI_Agent_Systems.md` — Implementation guide

### Supporting Documents
- `requirements_traceability_matrix.md` — Maps requirements to architecture components, test strategies, and acceptance criteria
- `srs_gap_analysis.md` — Documents all changes from SRS v1.0 to v2.0 with rationale
- `colette_vs_openclaw_comparison.md` — Competitive analysis against OpenClaw

### Research Documents
- `compass_artifact_wf-94ffe879*.md` — Agent orchestration patterns and topologies
- `compass_artifact_wf-b51e327d*.md` — Agentic memory systems: bi-temporal graphs, decay, scoping
- `compass_artifact_wf-f571ba0b*.md` — Context management: RAG pipelines, compression, hallucination defense

### Archives (.docx originals)
- `Colette_Software_Requirements_Specification.docx`, `MultiAgent_SDLC_System_Architecture.docx`, `Complete_Guide_to_Building_AI_Agent_Systems.docx`

## Document Versions

| Document | Version | Updated | Notes |
|---|---|---|---|
| `CLAUDE.md` | 3.0 | 2026-03-29 | Added project structure, dev commands, versioning scheme |
| `Colette_Software_Requirements_Specification.md` | 2.0 | 2026-03-29 | 164 requirements, MoSCoW, IEEE 830 |
| `MultiAgent_SDLC_System_Architecture.md` | 1.0 | 2026-03-29 | Full architecture doc |
| `Complete_Guide_to_Building_AI_Agent_Systems.md` | 1.0 | 2026-03-29 | Implementation guide |
| `requirements_traceability_matrix.md` | 1.0 | 2026-03-29 | Req → arch → test mapping |
| `srs_gap_analysis.md` | 1.0 | 2026-03-29 | SRS v1.0 → v2.0 delta |
| `colette_vs_openclaw_comparison.md` | 1.0 | 2026-03-29 | Competitive analysis |

## Project Structure

```
colette/
├── src/colette/              # Source package (src-layout)
│   ├── __init__.py           # Package root, __version__
│   ├── cli.py                # CLI entry point (Click)
│   ├── config.py             # Settings via pydantic-settings
│   ├── schemas/              # Typed Pydantic handoff schemas (FR-ORC-020)
│   │   ├── __init__.py
│   │   └── base.py           # HandoffSchema base class
│   ├── orchestrator/         # Project Orchestrator (FR-ORC-001)
│   ├── stages/               # Six SDLC pipeline stages
│   │   ├── requirements/     # NL → PRD (FR-REQ-*)
│   │   ├── design/           # PRD → architecture (FR-DES-*)
│   │   ├── implementation/   # Design → code (FR-IMP-*)
│   │   ├── testing/          # Code → test reports (FR-TST-*)
│   │   ├── deployment/       # Tested → deployed (FR-DEP-*)
│   │   └── monitoring/       # Observability (FR-MON-*)
│   ├── memory/               # Memory layer: hot/warm/cold (FR-MEM-*)
│   ├── tools/                # MCP tool integration (FR-TL-*)
│   ├── gates/                # Quality gate enforcement (§12)
│   └── human/                # Human-in-the-loop (FR-HIL-*)
├── tests/                    # Test suite (mirrors src/)
│   ├── conftest.py           # Shared fixtures
│   ├── unit/                 # Fast, no external deps
│   ├── integration/          # Requires services
│   └── e2e/                  # Full pipeline tests
├── docs/                     # Specification & architecture docs
├── scripts/                  # Utility scripts
├── pyproject.toml            # Project metadata, deps, tool configs
├── Makefile                  # Dev command shortcuts
├── Dockerfile                # Multi-stage container build
├── docker-compose.yml        # Dev services (postgres, redis, neo4j)
├── .env.example              # Environment variable template
├── CHANGELOG.md              # Keep-a-Changelog format
└── .github/workflows/ci.yml  # CI pipeline
```

## Versioning

- **Application:** Semantic Versioning (`MAJOR.MINOR.PATCH`) — single source of truth in `pyproject.toml` and `src/colette/__init__.py`
- **Handoff schemas:** Semantic versioning per schema, major bump on breaking changes (FR-ORC-021)
- **CLAUDE.md:** Integer version in header, changelog at bottom
- **Changelog:** `CHANGELOG.md` in Keep-a-Changelog format

## Changelog

### v3.0 — 2026-03-29
- Added project structure, directory layout, source packages
- Added `pyproject.toml` with all deps, ruff/mypy/pytest configs
- Added Dockerfile, docker-compose.yml, Makefile, CI workflow
- Added versioning scheme documentation

### v2.0 — 2026-03-29
- Added document version registry
- Added changelog section
- Added version/status header

### v1.0 — 2026-03-29
- Initial CLAUDE.md: project overview, tech stack, architecture, design constraints, doc reference, dev environment

## Development Environment

```bash
# ── Setup ──────────────────────────────────────────────────
make install               # uv sync (all deps)
make dev                   # install + create .env from template

# ── Quality ────────────────────────────────────────────────
make lint                  # ruff check
make format                # ruff format + fix
make typecheck             # mypy strict mode
make test                  # pytest with coverage (80% min)
make test-unit             # unit tests only
make security              # bandit + pip-audit

# ── Docker ─────────────────────────────────────────────────
make docker-up             # start postgres, redis, neo4j
make docker-down           # stop services
make docker-build          # build colette image

# ── All checks ─────────────────────────────────────────────
make check                 # lint + typecheck + test + security

# ── Direct uv commands ─────────────────────────────────────
uv run python <script>     # Run with venv
uv run colette --version   # CLI
```
