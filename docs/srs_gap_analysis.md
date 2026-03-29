# SRS Gap Analysis Report

**Version:** 1.0
**Date:** March 29, 2026
**Scope:** Changes from SRS v1.0 (2026-03-28) to SRS v2.0 (2026-03-29)

---

## 1. Structural Changes

| Change | Rationale |
| --- | --- |
| Added IEEE 830 / ISO 29148 compliance declaration | Industry standard for SRS documents; establishes credibility with enterprise stakeholders |
| Added populated Table of Contents with section links | v1.0 had empty ToC heading; navigability is essential for a 160+ requirement document |
| Added Section 1.6 (References) | IEEE 830 requires explicit references to companion documents |
| Added Section 2 (Overall Description) with subsections 2.1–2.6 | IEEE 830 §2 is mandatory; v1.0 jumped from Introduction directly to requirements |
| Added Section 2.4 (Operating Environment) | Documents runtime dependencies; critical for deployment planning |
| Added Section 2.5 (Design Constraints) as a table | v1.0 had constraints in §2.3 but as prose; tabular format with rationale improves clarity |
| Added Section 2.6 (Assumptions and Dependencies) | IEEE 830 §2.5; documents assumptions that if invalid would change system scope |
| Added Section 16 (Appendices) with glossary cross-ref, ID scheme, and architecture cross-reference | IEEE 830 appendices; ID scheme documentation prevents ID assignment confusion |
| Reformatted user stories from single-cell tables to heading + body format | v1.0 user stories were encoded in single-cell tables (Word artifact); unreadable in Markdown |
| Added user stories to Testing, Deployment, Monitoring, Memory, HIL, Tools, Quality Gates sections | v1.0 only had user stories for Requirements, Design, and Implementation stages |
| Added change history row to document metadata table | Version tracking for the SRS itself |

## 2. Requirements Added (23 new requirements)

| ID | Requirement | Source | Rationale |
| --- | --- | --- | --- |
| FR-ORC-017 | Tool count limit (≤5 per agent) | Orchestration research: tool selection accuracy drops below 80% beyond 15-20 tools | Prevents agent confusion from tool overload; research shows 3-5 tools optimal |
| FR-ORC-018 | Circuit breaker | Orchestration research: 5-layer resilience stack | Prevents cascading failures when an agent enters a failure loop |
| FR-ORC-025 | Handoff latency (<200ms p95) | Architecture doc: GuruSup benchmark | Makes handoff performance a testable requirement |
| FR-MEM-011 | Memory write quality gates | Memory research: Mem0 extraction pipeline | Prevents memory pollution from unchecked writes; 26% improvement over naive approach |
| FR-MEM-012 | Memory decay policy | Memory research: FadeMem bi-layer model | Prevents unbounded memory growth; 82.1% critical fact retention at 55% storage |
| FR-MEM-013 | RAG evaluation (RAG Triad) | Context research: RAGAS framework | Without evaluation, RAG quality degrades silently; faithfulness <0.85 indicates unreliable retrieval |
| NFR-PER-009 | Context compaction speed | Context research: Morph Compact benchmarks | Makes compaction speed a testable requirement (≥33K tokens/sec) |
| NFR-PER-010 | Handoff latency | Architecture doc: performance targets | Quantifies handoff performance expectation |
| NFR-REL-008 | Rollback success rate | Architecture doc: deployment reliability | Makes automated rollback reliability testable |
| NFR-SEC-009 | MCP tool poisoning defense | Context research: active attack vector | OWASP LLM Top 10; MCP tool descriptions can be manipulated |
| NFR-SEC-010 | Memory poisoning defense | Memory research: confidence-gated writes | Prevents adversarial or erroneous memory injection |
| NFR-SEC-011 | Inter-agent privilege isolation | Orchestration research: 82.4% of models compromised in escalation tests | Prevents privilege escalation via peer agent requests |
| NFR-OBS-006 | RAG pipeline monitoring | Context research: RAGAS metrics | Operational visibility into retrieval quality; alerts on faithfulness regression |
| WNT-011 | Messaging channel integration | OpenClaw comparison: 24-channel reach | Documented as future roadmap; not needed for v1.0 core functionality |
| WNT-012 | Lightweight local-only mode | OpenClaw comparison: lower barrier to entry | SQLite-backed mode for developers who don't need full stack |
| US-TST-001 | Testing stage user story | Gap: v1.0 had no user story for testing | Every stage should have at least one user story |
| US-DEP-001 | Deployment user story | Gap: v1.0 had no user story for deployment | Production approval flow needs user-facing acceptance criteria |
| US-MON-001 | Monitoring user story | Gap: v1.0 had no user story for monitoring | Operations team needs defined expectations |
| US-MEM-001 | Memory user story | Gap: v1.0 had no user story for memory | Cross-session memory behavior needs acceptance criteria |
| US-HIL-001 | Human-in-the-loop user story | Gap: v1.0 had no user story for HIL | Review experience needs acceptance criteria |
| US-TL-001 | Tools user story | Gap: v1.0 had no user story for tools | Admin tool configuration needs acceptance criteria |
| US-QG-001 | Quality gates user story | Gap: v1.0 had no user story for quality gates | Gate behavior needs acceptance criteria |

## 3. Requirements Modified (improved testability)

| ID | Change | Rationale |
| --- | --- | --- |
| FR-ORC-003 | Added "within 5 seconds of any stage transition" | Original was vague about persistence timing |
| FR-ORC-006 | Changed "multiple" to "at least 5" | Original lacked quantified concurrency target |
| FR-ORC-007 | Added "updated within 2 seconds of state changes" | Original said "real-time" without defining latency |
| FR-ORC-011 | Added warning at 80% of iteration limit | Research recommends pre-escalation warnings |
| FR-ORC-013 | Added "Each step SHALL be logged with rationale" | Original didn't require logging of escalation decisions |
| FR-ORC-014 | Added "p95 > 60s" threshold and explicit fallback chain | Original said "exceeds latency thresholds" without specifying |
| FR-REQ-001 | Added min/max input length (50–50,000 chars) | Original had no bounds on input size |
| FR-REQ-002 | Added "within 30 seconds" per clarification round | Original had no latency target for clarification |
| FR-MEM-002 | Added bi-temporal query details (4 timestamps) | Research identifies bi-temporal tracking as critical for SDLC systems |
| FR-MEM-003 | Expanded to three explicit scoping tiers (Private/Shared/Global) | Original was vague about scoping mechanism |
| FR-MEM-004 | Added specific budget allocation percentages | Architecture doc specifies allocation; SRS should too |
| FR-MEM-005 | Added "50–70% size reduction" and "≥98% verbatim accuracy" targets | Original said "auto-compaction" without measurable outcomes |
| FR-MEM-007 | Added RRF fusion parameter (k=60), candidate counts (50→5) | Original listed components but not configuration |
| FR-MEM-009 | Added "hybrid LLI+LLM contradiction detection" | Original said "flag the conflict" without specifying detection method |
| FR-HIL-002 | Added escalation rate target (10-15% of T2 actions) | Architecture doc specifies target; SRS should enforce |
| FR-TL-005 | Added 90-day retention requirement | Original had no retention policy |
| NFR-SEC-001 | Added three-layer defense description and <10% target | Original was too vague about defense mechanism |
| NFR-SEC-005 | Added 1-year retention requirement | Original had no audit log retention policy |
| NFR-USA-002 | Added API versioning requirement | Original said "documented REST API" but no versioning strategy |
| NFR-USA-004 | Added "within 2 seconds" latency | Original said "real-time" without defining it |

## 4. Metadata Corrections

| Issue | v1.0 | v2.0 | Rationale |
| --- | --- | --- | --- |
| Total requirement count | Header said 127; summary table showed 141 | 164 (after additions) | Resolved inconsistency; actual count is authoritative |
| Concurrent project target | Mentioned in two places with different numbers | Standardized to 5 (FR-ORC-006, NFR-SCA-002) | Eliminated conflicting numbers |
| NFR-PER-001 metric | "≥2 concurrent projects" | "≥5 concurrent projects" | Aligned with NFR-SCA-002 and architecture doc |

## 5. Requirements Not Changed

The following v1.0 requirements were preserved without modification, as they already met testability and completeness criteria:

- All FR-DES-* (Design Stage) — well-specified with measurable outputs
- All FR-IMP-* (Implementation Stage) — concrete code generation requirements
- All FR-TST-* (Testing Stage) — specific thresholds and tool requirements
- Most FR-DEP-* (Deployment) — specific infrastructure outputs
- All FR-MON-* (Monitoring) — specific metric and alert requirements
- All NFR-SCA-* (Scalability) — quantified targets
- Quality Gates (§12) — measurable pass/fail criteria

## 6. Consistency Verification

| Check | Result |
| --- | --- |
| No two requirements have the same ID | PASS |
| No two requirements specify the same thing | PASS |
| No two requirements contradict each other | PASS |
| All MUST requirements form a coherent MVP | PASS |
| Every architecture component has ≥1 governing requirement | PASS (see §16.3) |
| LiteLLM is used consistently (not "Portkey") | PASS — standardized on LiteLLM per architecture doc |
| Requirement ID scheme is consistent | PASS — documented in §16.2 |
| All sections have at least one user story | PASS (added in v2.0) |
