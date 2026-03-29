# Requirements Traceability Matrix

**Version:** 1.0
**Date:** March 29, 2026
**Scope:** Maps SRS v2.0 requirements to architecture components, test strategies, and acceptance criteria.

---

## 1. Orchestration Engine → Architecture

| Requirement | Architecture Component (REF-001) | Test Strategy | Acceptance Criterion |
| --- | --- | --- | --- |
| FR-ORC-001 | §2 Pipeline Stage Architecture | Integration test: run 6-stage pipeline, verify sequential execution | Stages execute in order; no stage starts before predecessor gate passes |
| FR-ORC-002 | §3.4 Implementation Agents (fan-out) | Integration test: verify parallel agent execution within Implementation | Frontend, Backend, DB agents run concurrently; all complete before supervisor merges |
| FR-ORC-003 | §10.1 LangGraph + Redis checkpointing | Integration test: pause at gate, kill process, resume | State persists; resume produces identical outcome |
| FR-ORC-004 | §2 Pipeline Stage Architecture | Integration test: complete 3 stages, rollback to stage 1 | Stage 1 checkpoint restored; stages 2-3 artifacts discarded |
| FR-ORC-005 | §2 Pipeline Stage Architecture | Config test: set skip_stages=["Deployment"] | Pipeline completes without Deployment stage |
| FR-ORC-006 | §10.3 Scaling Considerations | Load test: launch 5 concurrent pipelines | All 5 complete; no cross-project state leakage |
| FR-ORC-007 | §9.3 Observability Stack | API test: query progress endpoint during pipeline run | Response includes stage, agent status, gate results, timing; updates <2s |
| FR-ORC-008 | §2 Pipeline Stage Architecture | Config test: add custom stage to pipeline | Custom stage executes at configured position |
| FR-ORC-010 | §3 Agent Catalog (all agents) | Unit test: agent instantiation with role, prompt, tools, budget | Agent starts with correct configuration; no state from prior runs |
| FR-ORC-011 | §3 Agent Catalog | Integration test: agent loops 25+ times | Escalation triggers at limit; warning emitted at iteration 20 |
| FR-ORC-012 | §3 Agent Catalog | Integration test: agent runs >10 minutes | Graceful termination; state preserved |
| FR-ORC-013 | §8.3 Compaction Triggers (concat-and-retry) | Fault injection: force agent failure | Retry sequence follows 4-step order; all steps logged |
| FR-ORC-014 | §10.2 LLM Provider Strategy | Fault injection: primary provider returns 503 | Automatic failover to secondary model; response returned |
| FR-ORC-015 | §9.3 Observability Stack | Trace verification: check OTel spans after agent run | All fields present: agent_id, model, tokens, tools, duration, outcome |
| FR-ORC-016 | §3 Agent Catalog | Integration test: update agent prompt, run agent | New prompt used without platform restart |
| FR-ORC-017 | §7.1 MCP Server Architecture | Config test: attempt to assign >5 tools | System rejects or warns; assignment limited to 5 |
| FR-ORC-018 | §3 Agent Catalog | Fault injection: fail agent 3 times in <5 min | Circuit breaker activates; subsequent calls blocked for cooldown period |
| FR-ORC-020 | §4 Inter-Stage Handoff Contracts | Unit test: send malformed handoff schema | Receiving stage rejects with structured error |
| FR-ORC-021 | §4.1 Handoff Schema Design Principles | Unit test: send schema with version mismatch | System rejects; logs incompatibility |
| FR-ORC-022 | §4.1 Handoff Schema Design Principles | Unit test: inspect handoff content | Only permitted fields present; no raw LLM outputs |
| FR-ORC-023 | §4 Inter-Stage Handoff Contracts | Integration test: complete pipeline, check Git | Handoff JSON files exist in repo |
| FR-ORC-024 | §4.1 Handoff Schema Design Principles | Unit test: generate handoff exceeding 8K tokens | System compresses or links by reference |
| FR-ORC-025 | §4 Inter-Stage Handoff Contracts | Performance test: measure handoff latency | p95 < 200ms |

## 2. Requirements Stage → Architecture

| Requirement | Architecture Component | Test Strategy | Acceptance Criterion |
| --- | --- | --- | --- |
| FR-REQ-001 | §3.2 Requirements Analyst | Integration test: submit NL input | Accepts 50–50,000 chars; rejects outside range |
| FR-REQ-002 | §3.2 Requirements Analyst | Integration test: ambiguous input | Clarifying questions generated; max 5 rounds; <30s each |
| FR-REQ-003 | §3.2 Requirements Supervisor | Integration test: full PRD generation | PRD contains all required sections |
| FR-REQ-004 | §3.2 Domain Researcher | Integration test: generate PRD with research | Research results include source URLs |
| FR-REQ-005 | §3.2 Domain Researcher | Integration test: user specifies "Python only" | Recommendation respects constraint |
| FR-REQ-006 | §9.1 Quality Gates (Req→Design) | Unit test: score PRD completeness | Score ≥0.85 passes gate; <0.85 blocks |
| FR-REQ-007 | §4.2 Handoff Schemas | Integration test: trace user story ID through pipeline | ID persists from PRD to test report |
| FR-REQ-008 | §3.2 Requirements Analyst | Integration test: upload PDF | Relevant content extracted and incorporated |

## 3. Design Stage → Architecture

| Requirement | Architecture Component | Test Strategy | Acceptance Criterion |
| --- | --- | --- | --- |
| FR-DES-001 | §3.3 System Architect | Integration test: generate architecture doc | Contains component diagram, data flow, tech stack, rationale |
| FR-DES-002 | §3.3 API Designer | Integration test: generate API spec | Valid OpenAPI 3.1; zero validation errors |
| FR-DES-003 | §3.3 System Architect | Integration test: generate DB schema | Schema normalized to 3NF; denormalization justified in ADR |
| FR-DES-004 | §3.3 UI/UX Designer | Integration test: generate UI spec | Contains component hierarchy, props, layouts, navigation |
| FR-DES-005 | §3.3 System Architect | Integration test: generate ADRs | Each follows Title/Status/Context/Decision/Consequences format |
| FR-DES-006 | §3.3 Design Supervisor | Integration test: generate task graph | DAG with descriptions, complexity, dependencies, order |
| FR-DES-007 | §11 Security Architecture | Integration test: generate security design | Addresses all OWASP Top 10 risks |
| FR-DES-008 | §3.3 API Designer | Unit test: validate generated spec | OpenAPI 3.1 validation passes with zero errors |

## 4. Memory & Context → Architecture

| Requirement | Architecture Component | Test Strategy | Acceptance Criterion |
| --- | --- | --- | --- |
| FR-MEM-001 | §5.3 Project Memory (Mem0) | Integration test: persist decision, new session, retrieve | Decision retrieved in new session; scoped by project_id |
| FR-MEM-002 | §5.2 Codebase Knowledge Graph | Integration test: create entities, query relationships | Graph stores entities with bi-temporal timestamps; temporal queries work |
| FR-MEM-003 | §5.4 Memory Scoping Rules | Integration test: Implementation agent queries Deployment memory | Access denied; logged |
| FR-MEM-004 | §8.1 Per-Agent Context Budget | Integration test: monitor agent context usage | Agent stays within budget; allocation matches specified percentages |
| FR-MEM-005 | §8.3 Compaction Triggers | Integration test: fill agent context to 70% | Compaction triggers; 50-70% reduction; ≥98% verbatim accuracy on code |
| FR-MEM-007 | §8.2 Code-Specific Context Strategies | Integration test: RAG retrieval on codebase | Hybrid search returns relevant results; reranking improves precision |
| FR-MEM-009 | §5.3 Project Memory | Integration test: write contradictory memories | Conflict flagged for human resolution; not silently overwritten |
| FR-MEM-011 | §5.3 Project Memory | Integration test: write duplicate memory | Duplicate detected; existing memory updated instead of duplicated |
| FR-MEM-013 | §9.3 Observability Stack (RAGAS) | Integration test: monitor RAG quality | Triad metrics tracked; alert fires when faithfulness <0.85 |

## 5. Security → Architecture

| Requirement | Architecture Component | Test Strategy | Acceptance Criterion |
| --- | --- | --- | --- |
| NFR-SEC-001 | §11.1 Threat Model (prompt injection) | Security test: inject malicious prompt in user input | Attack success rate <10% |
| NFR-SEC-002 | §11.1 Threat Model (secret exfiltration) | Security test: search agent context for secrets | No secrets found in context, logs, Git, or traces |
| NFR-SEC-003 | §11.2 Sandboxing Model | Security test: attempt host filesystem access from sandbox | Access denied; execution confined |
| NFR-SEC-004 | §7.1 MCP Server Architecture | Security test: attempt to install unpinned MCP server | System rejects; integrity verification fails |
| NFR-SEC-009 | §11.1 Threat Model (MCP tool poisoning) | Security test: MCP server returns malicious tool description | Quarantined processing; no consequential action triggered |
| NFR-SEC-010 | §11.1 Threat Model (memory poisoning) | Security test: inject false high-importance memory | Confidence gate triggers human audit |
| NFR-SEC-011 | §7.2 Tool Access Control | Security test: agent attempts to access unauthorized tool via peer | Privilege escalation blocked |

## 6. Non-Functional → Architecture

| Requirement | Architecture Component | Test Strategy | Acceptance Criterion |
| --- | --- | --- | --- |
| NFR-PER-001 | §10.3 Scaling Considerations | Load test: 5 concurrent pipelines | All complete within acceptable latency |
| NFR-PER-006 | §8.1 Per-Agent Context Budget | Performance test: measure agent invocation time | p95 < 60 seconds |
| NFR-PER-007 | §8.2 Code-Specific Context Strategies | Performance test: measure RAG pipeline end-to-end | p95 < 500ms |
| NFR-REL-001 | §9.2 Agent Performance Metrics | Statistical test: 20 pipeline runs | ≥85% complete without human intervention for T3 tasks |
| NFR-REL-007 | §9.2 Agent Performance Metrics | Audit test: sample 100 agent claims, verify grounding | <5% ungrounded claims |
| NFR-OBS-001 | §9.3 Observability Stack | Trace test: verify OTel spans | Hierarchical traces for all agent invocations, tool calls, handoffs |
| NFR-OBS-006 | §9.3 Observability Stack (RAGAS) | Monitoring test: verify RAG metrics dashboard | Triad metrics visible; alert fires on faithfulness regression |
