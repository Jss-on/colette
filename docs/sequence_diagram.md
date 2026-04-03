# Colette — Complete Process Sequence Diagram

## Full Pipeline Sequence (CLI Submit → Completion)

```mermaid
sequenceDiagram
    participant User as User (CLI)
    participant CLI as CLI (cli.py)
    participant API as FastAPI (api/routes)
    participant DB as Database
    participant BG as BackgroundTask
    participant Registry as ProjectStatusRegistry
    participant Runner as PipelineRunner
    participant Graph as LangGraph StateGraph
    participant EB as EventBus
    participant SSE as SSE Stream

    %% ═══════════════════════════════════════════
    %% PHASE 1: PROJECT SUBMISSION
    %% ═══════════════════════════════════════════

    User->>CLI: colette submit --name "app" --description "..."
    CLI->>API: POST /api/v1/projects {name, description, user_request}
    API->>DB: ProjectRepository.create(project)
    DB-->>API: Project{id, status="created"}
    API->>DB: ProjectRepository.update_status(id, "running")
    API->>DB: PipelineRunRepository.create(project_id, thread_id)
    API->>DB: db.commit()
    API->>BG: background_tasks.add_task(_run_pipeline_bg)
    API-->>CLI: 201 ProjectResponse{id, status="running"}

    %% ═══════════════════════════════════════════
    %% PHASE 2: STREAMING SETUP (SSE or WebSocket)
    %% ═══════════════════════════════════════════

    alt --activity=minimal or status (SSE)
        CLI->>API: GET /api/v1/projects/{id}/pipeline/events (SSE)
        API->>EB: event_bus.subscribe(project_id)
        EB-->>API: asyncio.Queue
        API-->>SSE: StreamingResponse(text/event-stream)
        Note over CLI,SSE: CLI receives stage-level events via SSE
    else --activity=conversation or verbose (WebSocket)
        CLI->>API: WS /api/v1/projects/{id}/ws
        API->>EB: event_bus.subscribe(project_id)
        EB-->>API: asyncio.Queue
        API-->>CLI: WebSocket accepted
        API->>CLI: Catch-up events (completed stages)
        Note over CLI,SSE: CLI receives all events including AGENT_STREAM_CHUNK via WS
    end

    %% ═══════════════════════════════════════════
    %% PHASE 3: PIPELINE EXECUTION START
    %% ═══════════════════════════════════════════

    BG->>Registry: mark(project_id, "running")
    BG->>Runner: await runner.run(project_id, user_request)
    Runner->>Runner: thread_id = f"{project_id}-{uuid.hex[:8]}"
    Runner->>Runner: _active[project_id] = thread_id
    Runner->>Runner: initial = create_initial_state(project_id, user_request)
    Runner->>Graph: await graph.ainvoke(initial, config)
```

## Stage Execution Sequence (Per-Stage Pattern)

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant SN as StageNode
    participant EB as EventBus
    participant Sup as Supervisor
    participant Agent1 as Specialist Agent 1
    participant Agent2 as Specialist Agent 2
    participant Struct as invoke_structured()
    participant Guard as GuardedChatModel
    participant Reg as ProjectStatusRegistry
    participant LLM as LLM API (LiteLLM)
    participant CB as ColletteCallbackHandler

    Graph->>SN: _stage_node(state)
    SN->>EB: emit(STAGE_STARTED, stage_name)
    EB-->>SN: (non-blocking broadcast to SSE subscribers)
    SN->>SN: Set context vars: event_bus_var, project_id_var, stage_var
    SN->>SN: stage_statuses[name] = "running"

    SN->>Sup: await supervise_{stage}(project_id, handoff, settings)

    %% Agent 1 (MUST)
    Sup->>Agent1: await run_{specialist_1}(input, settings)
    Agent1->>Struct: await invoke_structured(prompt, content, OutputModel, tier)
    Struct->>Struct: sanitize_output(user_content)
    Struct->>Struct: _build_structured_prompt(prompt, schema)
    Struct->>Guard: create_chat_model_for_tier(tier, settings)
    Guard->>Guard: _build_chat_model(primary) + .with_fallbacks([...])
    Struct->>CB: Create ColletteCallbackHandler(agent_id, role)

    rect rgb(230, 245, 255)
        Note over Struct,LLM: Concurrency-controlled LLM call
        Struct->>Struct: async with _llm_semaphore
        alt Event bus active → streaming mode
            Struct->>Guard: model.astream([SystemMsg, HumanMsg], callbacks)
            Guard->>Reg: assert_active(project_id)
            Reg-->>Guard: OK (status == "running")
            Guard->>LLM: API call (streaming)
            loop Token stream
                LLM-->>Guard: token chunk
                CB->>CB: Buffer token (50ms batch)
                CB->>EB: emit(AGENT_STREAM_CHUNK, batch)
            end
            LLM-->>Guard: Stream complete
            CB->>EB: emit(AGENT_STREAM_CHUNK, remaining)
        else No event bus → standard mode
            Struct->>Guard: await model.ainvoke([SystemMsg, HumanMsg], callbacks)
            Guard->>Reg: assert_active(project_id)
            Reg-->>Guard: OK
            Guard->>LLM: API call (with fallback chain)
            LLM-->>Guard: Raw response (JSON in markdown)
        end
        Guard-->>Struct: Full response text
        CB->>EB: emit(AGENT_THINKING / AGENT_MESSAGE)
    end

    Struct->>Struct: extract_json_block(response)
    Struct->>Struct: OutputModel.model_validate_json(json)
    Struct-->>Agent1: OutputModel instance
    Agent1-->>Sup: SpecialistResult

    %% Agent 2 (parallel or sequential)
    Sup->>Agent2: await run_{specialist_2}(input, settings)
    Note over Agent2,LLM: Same invoke_structured() pattern
    Agent2-->>Sup: SpecialistResult (or None if SHOULD + failed)

    Sup->>Sup: assemble_handoff(results...)
    Sup-->>SN: HandoffSchema

    SN->>SN: stage_statuses[name] = "completed"
    SN->>SN: handoffs[name] = handoff.to_dict()
    SN->>EB: emit(STAGE_COMPLETED, stage_name)
    SN-->>Graph: Return state updates
```

## Gate Evaluation & Approval Sequence

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant GN as GateNode
    participant Gate as QualityGate
    participant EB as EventBus
    participant ApprovalLogic as determine_approval_action()
    participant Runner as PipelineRunner
    participant Registry as ProjectStatusRegistry
    participant DB as Database
    participant CLI as CLI (TUI)
    participant API as FastAPI
    participant User as User

    Graph->>GN: _gate_node(state)
    GN->>Gate: await gate.evaluate(state)
    Gate->>Gate: Check criteria (thresholds, required fields)
    Gate-->>GN: QualityGateResult{passed, score, failure_reasons}

    alt Gate FAILED
        GN->>EB: emit(GATE_FAILED, gate_name, reasons)
        GN->>GN: quality_gate_results[gate] = result
        GN-->>Graph: Return gate_state
        Graph->>Graph: Router → "gate_failed" → END
    else Gate PASSED
        GN->>EB: emit(GATE_PASSED, gate_name, score)
        GN->>GN: quality_gate_results[gate] = result
        GN->>ApprovalLogic: determine_approval_action(tier, score, settings)

        alt Auto-Approve (score >= auto_approve_threshold)
            ApprovalLogic-->>GN: "auto_approve"
            GN-->>Graph: Return gate_state
            Graph->>Graph: Router → next stage
        else Requires Human Approval (T0/T1 or low confidence)
            ApprovalLogic-->>GN: "interrupt"
            GN->>GN: Create ApprovalRequest(tier, context, deadline)
            GN->>GN: approval_requests = [request.model_dump()]
            GN->>EB: emit(APPROVAL_REQUIRED, handoff_summary)

            rect rgb(255, 245, 230)
                Note over GN,User: Pipeline Pauses — Human-in-the-Loop
                GN->>Graph: interrupt(approval_request)
                Graph-->>Runner: GraphInterrupt exception
                Runner->>Registry: mark(project_id, "awaiting_approval")
                Runner->>Runner: Keep project_id in _active dict
                Runner-->>DB: Update status = "awaiting_approval"
            end

            EB-->>CLI: SSE: approval_required event
            CLI->>CLI: Display Rich TUI approval panel
            CLI->>User: [A] Approve  [R] Reject  [Q] Quit

            User->>CLI: Approve (with optional comment)
            CLI->>API: POST /approvals/{id}/approve
            API->>DB: ApprovalRecord.status = "approved"
            CLI->>API: POST /projects/{id}/pipeline/resume
            API->>Runner: await runner.resume(project_id)

            rect rgb(230, 255, 230)
                Note over Runner,Graph: Pipeline Resumes
                Runner->>Registry: mark(project_id, "running")
                Runner->>Graph: graph.ainvoke(Command(resume={"action":"approved"}), config)
                Graph->>GN: Resume from interrupt() point
                GN-->>Graph: Return gate_state
                Graph->>Graph: Router → next stage
            end
        end
    end
```

## Complete Pipeline Flow (All 6 Stages)

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant REQ as Requirements Stage
    participant REQ_G as Requirements Gate
    participant DES as Design Stage
    participant DES_G as Design Gate
    participant IMP as Implementation Stage
    participant IMP_G as Implementation Gate
    participant TST as Testing Stage
    participant TST_G as Testing Gate
    participant DEP as Deployment Stage
    participant STG_G as Staging Gate
    participant MON as Monitoring Stage
    participant EB as EventBus

    Note over Graph,EB: START → Pipeline Execution Begins

    %% ═══ REQUIREMENTS ═══
    rect rgb(240, 248, 255)
        Graph->>REQ: stage_requirements(state)
        Note over REQ: Analyst (MUST) + Researcher (SHOULD)
        REQ->>REQ: run_analyst() → AnalysisResult
        REQ->>REQ: run_researcher() → ResearchResult | None
        REQ->>REQ: assemble_handoff() → RequirementsToDesignHandoff
        REQ-->>Graph: handoffs["requirements"], completeness_score
    end

    Graph->>REQ_G: gate_requirements(state)
    REQ_G->>REQ_G: completeness >= 0.80? stories have criteria?
    REQ_G-->>Graph: QualityGateResult{passed, score}
    Note over Graph: May interrupt() for approval

    %% ═══ DESIGN ═══
    rect rgb(245, 240, 255)
        Graph->>DES: stage_design(state)
        Note over DES: Architect → API Designer + UI Designer
        DES->>DES: run_architect() → ArchitectureResult
        DES->>DES: run_api_designer(arch_context) → APIDesignResult
        DES->>DES: run_ui_designer(arch_context) → UIDesignResult
        DES->>DES: assemble → DesignToImplementationHandoff
        DES-->>Graph: handoffs["design"]
    end

    Graph->>DES_G: gate_design(state)
    DES_G->>DES_G: openapi_spec? architecture? tech_stack? db_entities?
    DES_G-->>Graph: QualityGateResult
    Note over Graph: May interrupt() for approval

    %% ═══ IMPLEMENTATION ═══
    rect rgb(240, 255, 240)
        Graph->>IMP: stage_implementation(state)
        Note over IMP: Frontend ∥ Backend ∥ Database (parallel)
        par Parallel Agent Execution
            IMP->>IMP: run_frontend() → FrontendResult
        and
            IMP->>IMP: run_backend() → BackendResult
        and
            IMP->>IMP: run_database() → DatabaseResult
        end
        IMP->>IMP: cross_review() → CrossReviewResult (optional)
        IMP->>IMP: assemble → ImplementationToTestingHandoff
        IMP-->>Graph: handoffs["implementation"] + generated_files
    end

    Graph->>IMP_G: gate_implementation(state)
    IMP_G->>IMP_G: lint? typecheck? build? files? git_ref?
    IMP_G-->>Graph: QualityGateResult
    Note over Graph: May interrupt() for approval

    %% ═══ TESTING ═══
    rect rgb(255, 255, 235)
        Graph->>TST: stage_testing(state)
        Note over TST: Unit ∥ Integration (parallel) → Security (sequential)
        par Parallel Test Generation
            TST->>TST: run_unit_tester() → UnitTestResult
        and
            TST->>TST: run_integration_tester() → IntegrationTestResult
        end
        TST->>TST: run_security_scanner() → SecurityScanResult (SHOULD)
        TST->>TST: assemble → TestingToDeploymentHandoff (readiness_score)
        TST-->>Graph: handoffs["testing"]
    end

    Graph->>TST_G: gate_testing(state)
    TST_G->>TST_G: coverage >= 80/70%? no CRITICAL? contracts? readiness >= 75?
    TST_G-->>Graph: QualityGateResult
    Note over Graph: May interrupt() for approval

    %% ═══ DEPLOYMENT ═══
    rect rgb(255, 240, 240)
        Graph->>DEP: stage_deployment(state)
        Note over DEP: CI/CD Engineer ∥ Infra Engineer (parallel)
        par Parallel Deployment Config
            DEP->>DEP: run_cicd_engineer() → CICDResult
        and
            DEP->>DEP: run_infra_engineer() → InfraResult
        end
        DEP->>DEP: assemble → DeploymentToMonitoringHandoff
        DEP-->>Graph: handoffs["deployment"]
    end

    Graph->>STG_G: gate_staging(state)
    STG_G->>STG_G: targets? health_checks? rollback? slo_targets?
    STG_G-->>Graph: QualityGateResult
    Note over Graph: May interrupt() for T0 approval (staging/production)

    %% ═══ MONITORING ═══
    rect rgb(245, 245, 245)
        Graph->>MON: stage_monitoring(state)
        Note over MON: Observability ∥ Incident Response (parallel)
        par Parallel Monitoring Setup
            MON->>MON: run_observability_agent() → ObservabilityResult
        and
            MON->>MON: run_incident_response() → IncidentResponseResult
        end
        MON->>MON: assemble → MonitoringResult (terminal)
        MON-->>Graph: handoffs["monitoring"], completed_at
    end

    Note over Graph,EB: END → Pipeline Complete
    Graph->>EB: emit(PIPELINE_COMPLETED)
```

## Data Flow: Handoff Chain

```mermaid
sequenceDiagram
    participant REQ as Requirements
    participant DES as Design
    participant IMP as Implementation
    participant TST as Testing
    participant DEP as Deployment
    participant MON as Monitoring

    Note over REQ: Input: user_request (natural language)

    REQ->>DES: RequirementsToDesignHandoff
    Note right of REQ: project_overview, functional_requirements[],<br/>nonfunctional_requirements[], tech_constraints[],<br/>assumptions[], out_of_scope[],<br/>completeness_score, open_questions[]

    DES->>IMP: DesignToImplementationHandoff
    Note right of DES: architecture_summary, tech_stack{},<br/>openapi_spec (JSON), endpoints[],<br/>db_entities[], migration_strategy,<br/>ui_components[], navigation_flows[],<br/>adrs[], security_design, tasks[]

    IMP->>TST: ImplementationToTestingHandoff
    Note right of IMP: git_repo_url, git_ref, files_changed[],<br/>implemented_endpoints[], openapi_spec_ref,<br/>env_vars{}, lint_passed, type_check_passed,<br/>build_passed, test_hints[]

    TST->>DEP: TestingToDeploymentHandoff
    Note right of TST: test_results[], overall_line_coverage,<br/>overall_branch_coverage, security_findings[],<br/>dependency_vulnerabilities[],<br/>contract_tests_passed, deploy_readiness_score,<br/>blocking_issues[]

    DEP->>MON: DeploymentToMonitoringHandoff
    Note right of DEP: deployment_id, targets[],<br/>docker_images[], ci_pipeline_url,<br/>git_ref, rollback_command,<br/>slo_targets{}, staging_approval,<br/>production_approval

    Note over MON: Output: MonitoringResult (terminal)<br/>generated_files[], slo_definitions[],<br/>alert_rules[], quality_gate_passed
```

## LLM Call Sequence (invoke_structured)

```mermaid
sequenceDiagram
    participant Agent as Specialist Agent
    participant IS as invoke_structured()
    participant Sem as _llm_semaphore
    participant Guard as GuardedChatModel
    participant Reg as ProjectStatusRegistry
    participant Primary as Primary Model
    participant FB1 as Fallback Model 1
    participant CB as CallbackHandler
    participant EB as EventBus

    Agent->>IS: invoke_structured(prompt, content, OutputModel, tier)
    IS->>IS: sanitize_output(content)
    IS->>IS: _build_structured_prompt(prompt, OutputModel.json_schema())
    IS->>Guard: create_chat_model_for_tier(tier, settings)
    Note over Guard: Wraps primary.with_fallbacks([fb1, fb2])
    IS->>CB: ColletteCallbackHandler(agent_id, role, model)
    IS->>IS: stream_enabled = event_bus_var.get() is not None

    IS->>Sem: async with _llm_semaphore
    activate Sem
    Guard->>Reg: assert_active(project_id)

    alt Project Active
        Reg-->>Guard: OK

        alt stream_enabled (event bus active)
            IS->>Guard: model.astream([SystemMsg, HumanMsg], callbacks=[cb])
            Guard->>Primary: API call (streaming)
            loop Token by token
                Primary-->>Guard: chunk
                Guard-->>IS: chunk.content
                CB->>CB: _token_buffer.append(token)
                alt 50ms elapsed since last flush
                    CB->>EB: emit(AGENT_STREAM_CHUNK, batched_tokens)
                end
                IS->>IS: chunks.append(chunk)
            end
            IS->>IS: full_text = "".join(chunks)
            CB->>EB: emit(AGENT_STREAM_CHUNK, remaining buffer)
        else not streaming
            IS->>Guard: await ainvoke([SystemMsg, HumanMsg], callbacks=[cb])
            Guard->>Primary: API call
            alt Primary Succeeds
                Primary-->>Guard: AIMessage(json_content)
            else Primary Fails (transient)
                Primary-->>Guard: Error
                Guard->>FB1: Fallback API call
                FB1-->>Guard: AIMessage(json_content)
            end
            Guard-->>IS: AIMessage
            IS->>IS: full_text = response.content
        end

    else Project Not Active
        Reg-->>Guard: ProjectNotActiveError
        Guard-->>IS: Raise ProjectNotActiveError
        Note over IS: Propagates up → stage fails gracefully
    end

    CB->>EB: emit(AGENT_THINKING)
    CB->>EB: emit(AGENT_MESSAGE, token_usage)
    deactivate Sem

    IS->>IS: extract_json_block(full_text)
    IS->>IS: OutputModel.model_validate_json(json_str)
    IS-->>Agent: OutputModel instance
```

## Error Handling & Circuit Breaker

```mermaid
sequenceDiagram
    participant Sup as Supervisor
    participant CB as CircuitBreaker
    participant Agent as Specialist Agent
    participant IS as invoke_structured()
    participant LLM as LLM API

    Sup->>CB: Check breaker.state
    alt Circuit CLOSED (normal)
        Sup->>Agent: await run_specialist(input, settings)
        Agent->>IS: invoke_structured(...)
        IS->>LLM: API call

        alt Success
            LLM-->>IS: Response
            IS-->>Agent: Result
            Agent-->>Sup: SpecialistResult
            Sup->>CB: breaker = breaker.record_success()
            Note over CB: New instance: failures reset, state=CLOSED
        else Failure
            LLM-->>IS: Error / Timeout
            IS-->>Agent: Exception
            Agent-->>Sup: Exception
            Sup->>CB: breaker = breaker.record_failure()
            Note over CB: New instance: failure_count++

            alt failure_count >= threshold (3)
                Note over CB: State → OPEN (tripped)
                Note over CB: Cooldown: 120 seconds
            end

            alt Agent is SHOULD (optional)
                Sup->>Sup: Log warning, continue with None
            else Agent is MUST (required)
                Sup-->>Sup: Propagate failure → stage fails
            end
        end

    else Circuit OPEN (tripped)
        Note over Sup,CB: All requests rejected immediately
        Sup->>Sup: Skip agent, use fallback or fail

    else Circuit HALF_OPEN (cooldown expired)
        Sup->>Agent: One probe request allowed
        alt Probe Succeeds
            Agent-->>Sup: Result
            Sup->>CB: breaker = breaker.record_success()
            Note over CB: State → CLOSED
        else Probe Fails
            Agent-->>Sup: Exception
            Sup->>CB: breaker = breaker.record_failure()
            Note over CB: State → OPEN (re-tripped)
        end
    end
```

## Event Flow & Streaming (SSE + WebSocket)

```mermaid
sequenceDiagram
    participant Stage as Stage/Gate Node
    participant CtxVar as ContextVars
    participant CB as CallbackHandler
    participant EB as EventBus
    participant Q as asyncio.Queue
    participant SSE as SSE Generator
    participant WS as WebSocket Handler
    participant CLI as CLI (Rich TUI)

    Note over Stage,CLI: Event emission path

    Stage->>CtxVar: Set event_bus_var, project_id_var, stage_var
    Stage->>EB: emit(PipelineEvent{STAGE_STARTED, project_id, stage})

    Note over CB: During LLM calls (streaming mode)...
    CB->>CtxVar: Read event_bus_var, project_id_var
    CB->>EB: emit(PipelineEvent{AGENT_THINKING})
    loop Token streaming (50ms batches)
        CB->>EB: emit(PipelineEvent{AGENT_STREAM_CHUNK, token_batch})
    end
    CB->>EB: emit(PipelineEvent{AGENT_MESSAGE, content, tokens})

    EB->>Q: queue.put_nowait(event) for each subscriber
    Note over EB: Non-blocking; drops if queue full (1000 max)

    alt SSE Transport (minimal/status modes)
        loop SSE Event Loop
            SSE->>Q: await asyncio.wait_for(queue.get(), timeout=heartbeat)
            alt Event received
                Q-->>SSE: PipelineEvent
                SSE->>CLI: data: {event_type, stage, detail}\n\n
                CLI->>CLI: Update progress table + agent panel
            else Timeout
                SSE->>CLI: : keepalive\n\n
            end
        end
    else WebSocket Transport (conversation/verbose modes)
        loop WS Event Loop
            WS->>Q: await asyncio.wait_for(queue.get(), timeout=heartbeat)
            alt Event received
                Q-->>WS: PipelineEvent
                WS->>CLI: JSON: {event_type, agent, message, ...}
                alt AGENT_STREAM_CHUNK
                    CLI->>CLI: Append to per-agent live buffer
                    CLI->>CLI: Update Live Output panel
                else AGENT_MESSAGE
                    CLI->>CLI: Clear agent buffer, update stream log
                else Stage/Gate event
                    CLI->>CLI: Update progress table
                end
            else Timeout
                WS->>CLI: JSON: {event_type: "heartbeat"}
            end
        end
    end

    Stage->>EB: emit(PIPELINE_COMPLETED)
    EB->>Q: Final event
    Q-->>CLI: PIPELINE_COMPLETED
    CLI->>CLI: Render summary panel
    Note over SSE,WS: Unsubscribe from event bus, close transport
```

## Agent Roster Per Stage

| Stage | Agent | Role | Priority | LLM Tier | Output Type |
|-------|-------|------|----------|----------|-------------|
| **Requirements** | Analyst | Extract user stories, NFRs, constraints | MUST | PLANNING | `AnalysisResult` |
| | Researcher | Supplement with tech research | SHOULD | PLANNING | `ResearchResult` |
| **Design** | Architect | System architecture, tech stack, ADRs | MUST | PLANNING | `ArchitectureResult` |
| | API Designer | OpenAPI spec, endpoint design | MUST | EXECUTION | `APIDesignResult` |
| | UI Designer | Component specs, navigation | MUST | EXECUTION | `UIDesignResult` |
| **Implementation** | Frontend Dev | React/Next.js code generation | MUST | EXECUTION | `FrontendResult` |
| | Backend Dev | API server code generation | MUST | EXECUTION | `BackendResult` |
| | Database Eng | Migration & schema generation | MUST | EXECUTION | `DatabaseResult` |
| | Cross-Reviewer | Frontend↔Backend integration | SHOULD | VALIDATION | `CrossReviewResult` |
| **Testing** | Unit Tester | Unit test generation | MUST | EXECUTION | `UnitTestResult` |
| | Integration Tester | Integration & contract tests | MUST | EXECUTION | `IntegrationTestResult` |
| | Security Scanner | SAST + dependency scan | SHOULD | VALIDATION | `SecurityScanResult` |
| **Deployment** | CI/CD Engineer | Pipeline configs (GH Actions, etc.) | MUST | EXECUTION | `CICDResult` |
| | Infra Engineer | K8s/Docker infrastructure | MUST | EXECUTION | `InfraResult` |
| **Monitoring** | Observability Agent | Logging, metrics, dashboards | MUST | EXECUTION | `ObservabilityResult` |
| | Incident Response | Alerts, runbooks, procedures | MUST | EXECUTION | `IncidentResponseResult` |

## Gate Thresholds

| Gate | Key Criteria | Approval Tier |
|------|-------------|---------------|
| **requirements** | completeness_score >= 0.80, all stories have acceptance_criteria | T2 (moderate) |
| **design** | openapi_spec present, architecture_summary, tech_stack, db_entities | T2 (moderate) |
| **implementation** | lint_passed, type_check_passed, build_passed, files non-empty | T2 (moderate) |
| **testing** | line_coverage >= 80%, branch >= 70%, no CRITICAL, readiness >= 75 | T1 (high) |
| **staging** | targets present, health_checks, rollback, slo_targets | T1 (high) |
| **production** | staging passed + human approval | T0 (critical) |
