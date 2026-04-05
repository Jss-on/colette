# Colette Mission Control -- Backend API Requirements

> Specifies every new or modified API endpoint, event type, database change, and persistence mechanism needed to support the UI redesign described in `01-vision-and-design-system.md`.

---

## 1. Existing API Inventory (What Already Works)

| Endpoint | Method | Status |
|----------|--------|--------|
| `POST /api/v1/projects` | Create project + start pipeline | OK |
| `GET  /api/v1/projects` | List projects (paginated) | OK |
| `GET  /api/v1/projects/{id}` | Get single project | OK |
| `POST /api/v1/projects/{id}/resume` | Resume interrupted project | OK |
| `POST /api/v1/projects/{id}/cancel` | Cancel project | OK |
| `GET  /api/v1/projects/{id}/pipeline` | Latest pipeline run | OK |
| `GET  /api/v1/projects/{id}/pipeline/events` | SSE stream | OK |
| `POST /api/v1/projects/{id}/pipeline/resume` | Resume after approval | OK |
| `GET  /api/v1/approvals` | List pending approvals | OK (needs enhancement) |
| `GET  /api/v1/approvals/{id}` | Get single approval | OK |
| `POST /api/v1/approvals/{id}/approve` | Approve gate | OK |
| `POST /api/v1/approvals/{id}/reject` | Reject gate | OK |
| `GET  /api/v1/projects/{id}/artifacts` | List artifacts | OK |
| `GET  /api/v1/projects/{id}/artifacts/download` | Download ZIP | OK |
| `GET  /api/v1/projects/{id}/agents` | Current agent presence | OK |
| `GET  /api/v1/projects/{id}/conversation` | Conversation buffer | OK (needs persistence) |
| `WS   /api/v1/projects/{id}/ws` | WebSocket events | OK (needs new event types) |
| `GET  /health`, `GET /ready`, `GET /version` | Health/readiness | OK |

---

## 2. New API Endpoints

### 2.1 Pipeline Run History

**Why**: The UI needs to show all past runs for a project, not just the latest one. Required for Run History page, run comparison, and analytics.

```
GET /api/v1/projects/{project_id}/runs
```

**Query parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | (all) | Filter: `running`, `completed`, `failed`, `cancelled` |
| `limit` | int | 20 | Page size (max 100) |
| `offset` | int | 0 | Pagination offset |

**Response** (`PipelineRunListResponse`):
```json
{
  "data": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "thread_id": "string",
      "status": "completed",
      "current_stage": "monitoring",
      "total_tokens": 42847,
      "started_at": "2026-04-05T14:22:01Z",
      "completed_at": "2026-04-05T14:35:22Z",
      "duration_seconds": 801,
      "stage_summary": {
        "requirements": {"status": "completed", "duration_seconds": 64, "tokens": 2200},
        "design": {"status": "completed", "duration_seconds": 82, "tokens": 5400},
        "implementation": {"status": "completed", "duration_seconds": 340, "tokens": 22000},
        "testing": {"status": "completed", "duration_seconds": 180, "tokens": 8200},
        "deployment": {"status": "completed", "duration_seconds": 90, "tokens": 3100},
        "monitoring": {"status": "completed", "duration_seconds": 45, "tokens": 1947}
      }
    }
  ],
  "total": 5,
  "offset": 0,
  "limit": 20
}
```

**Implementation**: Query `pipeline_runs` table joined with `stage_executions` for summary. The `stage_summary` field is computed by aggregating `stage_executions` rows for each run.

**File**: `src/colette/api/routes/pipelines.py` (new endpoint in existing router)

---

### 2.2 Stage Execution Details

**Why**: The Board and Pipeline views need per-stage metrics with gate results. The `stage_executions` table exists but is not exposed.

```
GET /api/v1/runs/{run_id}/stages
```

**Response** (`StageExecutionListResponse`):
```json
{
  "data": [
    {
      "id": "uuid",
      "pipeline_run_id": "uuid",
      "stage": "requirements",
      "status": "completed",
      "started_at": "2026-04-05T14:22:01Z",
      "completed_at": "2026-04-05T14:23:05Z",
      "duration_seconds": 64,
      "tokens_used": 2200,
      "gate_result": {
        "passed": true,
        "score": 0.92,
        "threshold": 0.85,
        "reasons": ["All required fields present", "12 user stories identified"],
        "needs_approval": false
      }
    }
  ]
}
```

**Implementation**: Direct query on `stage_executions` table filtered by `pipeline_run_id`, ordered by `started_at`.

**File**: `src/colette/api/routes/pipelines.py` (new endpoint)

---

### 2.3 Approval History (Enhanced)

**Why**: The Decision Rail needs to show all approvals (not just pending ones) as a chronological audit trail.

```
GET /api/v1/approvals
```

**New query parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `project_id` | uuid | (optional) | Filter by project |
| `status` | string | `pending` | Filter: `pending`, `approved`, `rejected`, `all` |
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Pagination offset |

**Change**: Currently only returns `pending`. Add `status=all` support by removing the hardcoded `pending` filter in the query.

**File**: `src/colette/api/routes/approvals.py` (modify existing endpoint)

---

### 2.4 Individual Artifact Content

**Why**: The Artifact Workshop needs to display individual file content with syntax highlighting, not just ZIP download.

```
GET /api/v1/projects/{project_id}/artifacts/{artifact_id}/content
```

**Response**: Raw file content with appropriate `Content-Type` header.

For text files: `text/plain`, `application/json`, `text/yaml`, etc.

**Query parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string | `raw` | `raw` returns file content, `preview` returns first 500 lines |

**Implementation**: Look up artifact in `state_snapshot.metadata.generated_files` or `state_snapshot.handoffs.*.generated_files` by matching the `path` field. Return the `content` field.

**File**: `src/colette/api/routes/artifacts.py` (new endpoint)

---

### 2.5 Event History (Persisted)

**Why**: The Activity view and Run Replay need queryable event history, not just a live stream. Currently events are fire-and-forget through the in-memory event bus.

```
GET /api/v1/runs/{run_id}/events
```

**Query parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | (all) | Comma-separated event types: `stage_started,agent_thinking` |
| `stage` | string | (all) | Filter by stage name |
| `agent` | string | (all) | Filter by agent name |
| `limit` | int | 200 | Max events returned |
| `offset` | int | 0 | Pagination offset |
| `after` | ISO datetime | (none) | Events after this timestamp |

**Response** (`EventListResponse`):
```json
{
  "data": [
    {
      "event_type": "agent_thinking",
      "stage": "requirements",
      "agent": "@Researcher",
      "model": "claude-sonnet-4-6",
      "message": "Analyzing project requirements...",
      "detail": {},
      "timestamp": "2026-04-05T14:22:03Z",
      "elapsed_seconds": 2.1,
      "tokens_used": 0
    }
  ],
  "total": 847,
  "offset": 0,
  "limit": 200
}
```

**Requires**: New `pipeline_events` table (see section 4).

**File**: `src/colette/api/routes/pipelines.py` (new endpoint)

---

### 2.6 Agent Metrics per Run

**Why**: Tool Timeline and Agent Performance analytics need historical agent data, not just current in-memory presence.

```
GET /api/v1/runs/{run_id}/agents
```

**Response** (`AgentMetricsListResponse`):
```json
{
  "data": [
    {
      "agent_id": "@Researcher",
      "display_name": "Researcher",
      "stage": "requirements",
      "final_state": "done",
      "model": "claude-sonnet-4-6",
      "model_tier": "EXECUTION",
      "tokens_used": 1240,
      "duration_seconds": 32,
      "tool_calls": [
        {
          "tool_name": "filesystem.read",
          "status": "success",
          "duration_ms": 320,
          "timestamp": "2026-04-05T14:22:15Z"
        }
      ],
      "tool_call_count": 3,
      "tool_error_count": 0,
      "started_at": "2026-04-05T14:22:01Z",
      "completed_at": "2026-04-05T14:22:33Z"
    }
  ]
}
```

**Implementation**: Computed from persisted events (filtered by agent-level event types, aggregated).

**File**: `src/colette/api/routes/agents.py` (new endpoint)

---

### 2.7 Operator Intervention Endpoints

**Why**: The operator must be able to intervene at any point during pipeline execution -- pause, inject feedback, redirect agents, restart or skip stages. Currently only `cancel` and gate `approve`/`reject` exist.

#### 2.7.1 Pause Pipeline

```
POST /api/v1/projects/{project_id}/pause
```

**Request body**:
```json
{
  "reason": "Reviewing design output before implementation proceeds"
}
```

**Response**: `ProjectResponse` with `status: "paused"`

**Implementation**:
- Set a `paused` flag in `PipelineRunner` for this project (checked before each agent invocation and between agent calls within a supervisor).
- Agents finish their current LLM call, then stop. No new agent calls are dispatched.
- Emit `PIPELINE_PAUSED` event.
- Update project status to `paused` in DB.
- The existing `POST /projects/{id}/resume` endpoint handles un-pausing (extend it to also clear the `paused` flag, emit `PIPELINE_RESUMED`).

**File**: `src/colette/api/routes/projects.py`

#### 2.7.2 Inject Feedback

```
POST /api/v1/projects/{project_id}/feedback
```

**Request body**:
```json
{
  "message": "Use PostgreSQL instead of MongoDB for the database",
  "target_stage": "implementation",
  "target_agent": null
}
```

**Response**:
```json
{
  "status": "delivered",
  "injected_at": "2026-04-05T14:24:30Z",
  "target": "implementation supervisor"
}
```

**Implementation**:
- Append the message to `PipelineState.user_feedback` list (using LangGraph state update).
- If `target_agent` is specified, route to that agent's next context window.
- The supervisor's system prompt already includes a section for reading `user_feedback`. If not, add one: "Check for operator feedback in `state['user_feedback']` and incorporate it into your decisions."
- Emit `OPERATOR_FEEDBACK` event with the message and target.
- Works while pipeline is running (no need to pause first).

**File**: `src/colette/api/routes/projects.py`

#### 2.7.3 Send Message to Agent

```
POST /api/v1/projects/{project_id}/agents/{agent_id}/message
```

**Request body**:
```json
{
  "message": "Use JWT tokens instead of session cookies"
}
```

**Response**:
```json
{
  "status": "queued",
  "agent_id": "@Backend Dev",
  "delivered_at": null
}
```

**Implementation**:
- Queue the message in a per-agent message buffer (in-memory, keyed by project_id + agent_id).
- The agent's next LLM call picks up queued messages via the callback handler, prepending them to the user message.
- Emit `OPERATOR_MESSAGE` event.
- If the agent has already completed, return `status: "agent_completed"` (message cannot be delivered).

**File**: `src/colette/api/routes/agents.py`

#### 2.7.4 Restart Stage

```
POST /api/v1/projects/{project_id}/stages/{stage_name}/restart
```

**Request body**:
```json
{
  "reason": "Design output missed API pagination strategy"
}
```

**Response**: `ProjectResponse` with `status: "running"`, `current_stage` reset to the restarted stage.

**Implementation**:
- Validate that `stage_name` is the current or a completed stage (cannot restart a future stage).
- Clear the stage's output from `PipelineState.handoffs[stage_name]`.
- Reset `stage_statuses[stage_name]` to `PENDING`.
- Re-invoke the pipeline from that stage's node using LangGraph checkpoint replay.
- Emit `STAGE_RESTARTED` event.
- If pipeline was paused, restart un-pauses it.

**File**: `src/colette/api/routes/projects.py`

#### 2.7.5 Skip Stage

```
POST /api/v1/projects/{project_id}/stages/{stage_name}/skip
```

**Request body**:
```json
{
  "reason": "Requirements already defined externally",
  "synthetic_handoff": {
    "user_stories": [...],
    "nfrs": [...],
    "completeness_score": 0.95
  }
}
```

**Response**: `ProjectResponse` with next stage now active.

**Implementation**:
- Validate that `stage_name` is the current stage (cannot skip a completed or future stage).
- Write `synthetic_handoff` into `PipelineState.handoffs[stage_name]`.
- Mark stage as `completed` with a synthetic gate pass (score = 1.0, reasons = ["Skipped by operator"]).
- Advance the pipeline to the next stage.
- Emit `STAGE_SKIPPED` event.

**File**: `src/colette/api/routes/projects.py`

#### 2.7.6 Edit Handoff

```
PATCH /api/v1/projects/{project_id}/handoffs/{stage_name}
```

**Request body**:
```json
{
  "patch": {
    "user_stories": [
      {"id": "US-13", "title": "Admin dashboard", "priority": "should"}
    ]
  },
  "mode": "merge"
}
```

`mode`: `merge` (deep-merge patch into existing handoff) or `replace` (overwrite entirely).

**Response**: The updated handoff object.

**Implementation**:
- Read `PipelineState.handoffs[stage_name]`.
- Apply the patch (merge or replace).
- Write back to state via LangGraph checkpoint update.
- Emit `HANDOFF_EDITED` event with the diff.
- Can only edit a handoff that has been produced but whose next stage has not yet started.

**File**: `src/colette/api/routes/pipelines.py`

---

## 3. New Event Types

### 3.1 `ARTIFACT_GENERATED`

**Why**: The Artifact Workshop needs to show files as they're created, not only after pipeline completion.

```python
# In EventType enum:
ARTIFACT_GENERATED = "artifact_generated"
```

**Event detail**:
```json
{
  "event_type": "artifact_generated",
  "stage": "implementation",
  "agent": "@Backend Dev",
  "message": "Generated src/main.py",
  "detail": {
    "path": "src/main.py",
    "language": "python",
    "size_bytes": 2400,
    "content_preview": "from fastapi import FastAPI\n\napp = FastAPI()..."
  }
}
```

**Where to emit**: In `stages/<name>/stage.py` when `GeneratedFile` objects are created, or in the supervisor after agent output is collected.

**Frontend handling**: `ArtifactWorkshop` inserts the file into the file tree with a "new" indicator. If the file path matches an open preview tab, the content updates live.

### 3.2 Enhanced `AGENT_TOOL_CALL`

**Why**: The Tool Timeline needs tool arguments and results, not just the tool name.

**Current `detail` payload**:
```json
{
  "tool_name": "filesystem.read"
}
```

**Enhanced `detail` payload**:
```json
{
  "tool_name": "filesystem.read",
  "tool_call_id": "call_abc123",
  "status": "success",
  "duration_ms": 320,
  "arguments": {
    "path": "/src/main.py"
  },
  "result_preview": "from fastapi import FastAPI...",
  "error": null
}
```

**Where to emit**: In `ColletteCallbackHandler` (the LangChain callback handler), which already emits `AGENT_TOOL_CALL`. Enhance it to include the additional fields.

**Truncation**: `arguments` and `result_preview` must be truncated to max 500 chars each to avoid bloating the event stream.

### 3.3 `AGENT_TOOL_RESULT`

**Why**: Separate event for tool completion, enabling the Tool Timeline to show duration accurately.

```python
AGENT_TOOL_RESULT = "agent_tool_result"
```

**Detail**:
```json
{
  "tool_name": "terminal.exec",
  "tool_call_id": "call_abc123",
  "status": "error",
  "duration_ms": 2100,
  "result_preview": "Command failed: npm ERR! ...",
  "error": "Exit code 1"
}
```

**Where to emit**: In `ColletteCallbackHandler.on_tool_end()` and `on_tool_error()`.

### 3.4 Operator Intervention Events

**Why**: Every operator action must be recorded in the event stream for the Decision Rail, activity feed, and history replay.

```python
# In EventType enum:
PIPELINE_PAUSED = "pipeline_paused"
PIPELINE_RESUMED = "pipeline_resumed"
STAGE_RESTARTED = "stage_restarted"
STAGE_SKIPPED = "stage_skipped"
OPERATOR_FEEDBACK = "operator_feedback"
OPERATOR_MESSAGE = "operator_message"
HANDOFF_EDITED = "handoff_edited"
```

**Event details**:

| Event | Detail Fields |
|-------|---------------|
| `PIPELINE_PAUSED` | `reason`, `paused_by` |
| `PIPELINE_RESUMED` | `resumed_by`, `paused_duration_seconds` |
| `STAGE_RESTARTED` | `stage`, `reason`, `restarted_by` |
| `STAGE_SKIPPED` | `stage`, `reason`, `skipped_by`, `synthetic_handoff_keys` |
| `OPERATOR_FEEDBACK` | `message`, `target_stage`, `target_agent` (nullable) |
| `OPERATOR_MESSAGE` | `message`, `target_agent`, `delivery_status` |
| `HANDOFF_EDITED` | `stage`, `mode` (merge/replace), `edited_fields` |

**Where to emit**: In the respective API route handlers, after the action is performed.

---

## 4. Database Changes

### 4.1 New Table: `pipeline_events`

**Why**: Events are currently fire-and-forget through the in-memory `PipelineEventBus`. For history, replay, and analytics, they must be persisted.

```python
class PipelineEventRecord(Base):
    """Persisted pipeline event for history and replay."""

    __tablename__ = "pipeline_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    agent: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    elapsed_seconds: Mapped[float] = mapped_column(default=0.0)
    tokens_used: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    __table_args__ = (
        Index("ix_pipeline_events_run_id", "pipeline_run_id"),
        Index("ix_pipeline_events_type", "event_type"),
        Index("ix_pipeline_events_run_stage", "pipeline_run_id", "stage"),
    )
```

**Write path**: Add an async listener to `PipelineEventBus` that persists each event to the database. Use a background task with batching (e.g., flush every 500ms or every 50 events) to avoid slowing down the event pipeline.

**Exclusions**: Do NOT persist `AGENT_STREAM_CHUNK` events (too high volume, content available via agent output). Do NOT persist `heartbeat`.

**Migration**: Alembic migration to create the table.

### 4.2 New Table: `conversation_messages`

**Why**: The current `ConversationEntry` ring buffer is in-memory only, lost on restart. Agent conversations should be queryable.

```python
class ConversationMessage(Base):
    """Persisted agent conversation message."""

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    target_agent: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    __table_args__ = (
        Index("ix_conversation_messages_run_id", "pipeline_run_id"),
    )
```

**Write path**: When `AGENT_MESSAGE` events are emitted, the event persister also writes a `ConversationMessage` row.

**Read path**: The existing `GET /projects/{id}/conversation` endpoint should query this table (for the latest run) instead of the in-memory ring buffer, falling back to the ring buffer for currently-running pipelines.

### 4.3 Modification: `Artifact` Table Usage

The `artifacts` table already exists but is not actively populated during pipeline execution. Currently, artifacts are extracted from `state_snapshot` JSONB at query time.

**Change**: Write `Artifact` rows as `ARTIFACT_GENERATED` events are emitted. Store the `content` in the `storage_key` field (or add a `content` TEXT column for simplicity, since generated files are typically small).

**Option A -- Add content column**:
```python
# Add to Artifact model:
content: Mapped[str] = mapped_column(Text, nullable=False, default="")
stage: Mapped[str] = mapped_column(String(50), nullable=False, default="")
agent: Mapped[str] = mapped_column(String(255), nullable=False, default="")
```

**Option B -- Keep in state_snapshot**: No schema change. The individual artifact content endpoint reads from `state_snapshot`. Simpler but couples API to snapshot structure.

**Recommendation**: Option A for new artifacts going forward. The content endpoint falls back to state_snapshot for older runs.

---

## 5. Modifications to Existing Code

### 5.1 Event Bus: Add Persistence Listener

**File**: `src/colette/orchestrator/event_bus.py`

Add an `EventPersister` class that subscribes to the event bus and writes events to the `pipeline_events` table in batches.

```python
class EventPersister:
    """Subscribes to event bus and persists events to database."""

    def __init__(self, db_session_factory, batch_size=50, flush_interval=0.5):
        self._factory = db_session_factory
        self._batch: list[PipelineEvent] = []
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._skip_types = {EventType.AGENT_STREAM_CHUNK}

    async def handle(self, event: PipelineEvent) -> None:
        if event.event_type in self._skip_types:
            return
        self._batch.append(event)
        if len(self._batch) >= self._batch_size:
            await self._flush()

    async def _flush(self) -> None:
        if not self._batch:
            return
        async with self._factory() as session:
            for event in self._batch:
                session.add(PipelineEventRecord.from_event(event))
            await session.commit()
        self._batch.clear()
```

### 5.2 Callback Handler: Enhanced Tool Call Events

**File**: `src/colette/llm/callbacks.py` (or wherever `ColletteCallbackHandler` lives)

Modify `on_tool_start()` to include `arguments` in the `AGENT_TOOL_CALL` detail.

Modify `on_tool_end()` to emit a new `AGENT_TOOL_RESULT` event with status, duration, and result preview.

Modify `on_tool_error()` to emit `AGENT_TOOL_RESULT` with `status: "error"` and error message.

### 5.3 Stage Nodes: Emit `ARTIFACT_GENERATED`

**Files**: `src/colette/stages/*/stage.py`

After a specialist agent produces output that includes generated files, emit an `ARTIFACT_GENERATED` event for each file. This should happen in the supervisor after collecting agent output, not inside the agent itself.

### 5.4 Agent Presence: Conversation Persistence

**File**: `src/colette/api/routes/agents.py`

The `GET /projects/{id}/conversation` endpoint should:
1. If the project is currently running: return in-memory ring buffer (current behavior)
2. If the project is completed/failed: query `conversation_messages` table for the latest run

### 5.5 Approvals: Status Filter

**File**: `src/colette/api/routes/approvals.py`

Modify the list endpoint to accept `status` query parameter. When `status=all`, remove the `.where(ApprovalRecord.status == "pending")` filter.

---

## 6. New Pydantic Schemas

Add to `src/colette/api/schemas.py`:

```python
# --- Pipeline Run List ---

class StageSummary(BaseModel, frozen=True):
    status: str
    duration_seconds: float
    tokens: int

class PipelineRunSummary(BaseModel, frozen=True):
    id: uuid.UUID
    project_id: uuid.UUID
    thread_id: str
    status: str
    current_stage: str
    total_tokens: int
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float
    stage_summary: dict[str, StageSummary]

class PipelineRunListResponse(BaseModel, frozen=True):
    data: list[PipelineRunSummary]
    total: int
    offset: int
    limit: int


# --- Stage Execution ---

class GateResultDetail(BaseModel, frozen=True):
    passed: bool
    score: float
    threshold: float
    reasons: list[str]
    needs_approval: bool

class StageExecutionResponse(BaseModel, frozen=True):
    id: uuid.UUID
    pipeline_run_id: uuid.UUID
    stage: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float
    tokens_used: int
    gate_result: GateResultDetail | None

class StageExecutionListResponse(BaseModel, frozen=True):
    data: list[StageExecutionResponse]


# --- Event History ---

class EventResponse(BaseModel, frozen=True):
    event_type: str
    stage: str
    agent: str
    model: str
    message: str
    detail: dict[str, Any]
    timestamp: str
    elapsed_seconds: float
    tokens_used: int

class EventListResponse(BaseModel, frozen=True):
    data: list[EventResponse]
    total: int
    offset: int
    limit: int


# --- Agent Metrics ---

class ToolCallSummary(BaseModel, frozen=True):
    tool_name: str
    status: str
    duration_ms: float
    timestamp: str

class AgentMetrics(BaseModel, frozen=True):
    agent_id: str
    display_name: str
    stage: str
    final_state: str
    model: str
    model_tier: str
    tokens_used: int
    duration_seconds: float
    tool_calls: list[ToolCallSummary]
    tool_call_count: int
    tool_error_count: int
    started_at: str
    completed_at: str | None

class AgentMetricsListResponse(BaseModel, frozen=True):
    data: list[AgentMetrics]
```

---

## 7. WebSocket Enhancements

### 7.1 New Event Types in Stream

The WebSocket already sends all `PipelineEvent`s. The new event types (`ARTIFACT_GENERATED`, `AGENT_TOOL_RESULT`) will automatically flow to the frontend as long as they are emitted via the event bus.

**Frontend changes needed**: Add handlers in `pipeline.ts` store:

```typescript
// Add to EventType const:
ARTIFACT_GENERATED: 'artifact_generated',
AGENT_TOOL_RESULT: 'agent_tool_result',
```

### 7.2 Reconnection State Recovery

Currently, on WebSocket reconnect, the frontend fetches agent presence and conversation via REST. Enhance this to also fetch:
- Stage execution state (for accurate gate results)
- Pending approvals (for Decision Rail hydration)

**File**: `web/src/hooks/useWebSocket.ts` -- add REST calls on `open` event.

---

## 8. Summary: Files to Create/Modify

### New Files

| File | Description |
|------|-------------|
| `src/colette/db/models.py` | Add `PipelineEventRecord`, `ConversationMessage` models |
| `src/colette/orchestrator/event_persister.py` | Event bus -> DB persistence listener |
| `alembic/versions/xxxx_add_event_history.py` | Migration for new tables |

### Modified Files

| File | Change |
|------|--------|
| `src/colette/api/routes/pipelines.py` | Add `GET /runs`, `GET /runs/{id}/stages`, `GET /runs/{id}/events` |
| `src/colette/api/routes/agents.py` | Add `GET /runs/{id}/agents`, modify conversation endpoint |
| `src/colette/api/routes/artifacts.py` | Add `GET /artifacts/{id}/content` |
| `src/colette/api/routes/approvals.py` | Add `status` filter param |
| `src/colette/api/schemas.py` | Add new response schemas |
| `src/colette/orchestrator/event_bus.py` | Add `EventType.ARTIFACT_GENERATED`, `AGENT_TOOL_RESULT` |
| `src/colette/llm/callbacks.py` | Enhanced tool call detail in events |
| `src/colette/stages/*/stage.py` or supervisors | Emit `ARTIFACT_GENERATED` events |
| `src/colette/api/app.py` | Register event persister on startup |

### Frontend Files

| File | Change |
|------|--------|
| `web/src/types/events.ts` | Add new event types |
| `web/src/stores/pipeline.ts` | Handle new events, add artifact state |
| `web/src/hooks/useWebSocket.ts` | Enhanced reconnection hydration |
| `web/src/hooks/useApi.ts` | Add functions for new endpoints |
