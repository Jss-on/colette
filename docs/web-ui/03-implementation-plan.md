# Colette Mission Control -- Implementation Plan

> Phased roadmap turning the vision (`01-vision-and-design-system.md`) and API requirements (`02-backend-api-requirements.md`) into working code. Each phase is independently deployable and testable.

---

## Phase Overview

| Phase | Name | Scope | Backend | Frontend |
|-------|------|-------|---------|----------|
| **1** | Foundation | Design system + layout shell + Live Terminal | Minimal | Heavy |
| **2** | Event Persistence | Persist events + conversations to DB | Heavy | Light |
| **3** | War Room | Spatial stage rooms + agent cards | None | Heavy |
| **4** | Operator Intervention | Pause/feedback/restart/skip + Command Bar | Heavy | Heavy |
| **5** | Tool Visibility | Enhanced tool events + Tool Timeline | Medium | Medium |
| **6** | Artifact Workshop | Real-time artifact events + code preview | Medium | Heavy |
| **7** | Decision Rail | Approval history + notification system | Light | Medium |
| **8** | History & Analytics | Run history, replay, cost dashboard | Medium | Heavy |

Estimated effort: Each phase is 1-3 sessions of focused work.

---

## Phase 1: Foundation

**Goal**: Replace the current flat design with the Mission Control shell, design system, and the most impactful new component -- the Live Terminal.

### 1.1 Design System Setup

**Files to create/modify**:

| File | Action | Description |
|------|--------|-------------|
| `web/src/index.css` | Modify | Replace CSS variables with new design tokens from spec |
| `web/src/styles/tokens.css` | Create | Extract all design tokens (colors, spacing, typography, effects) |
| `web/tailwind.config.ts` | Modify | Extend with full color palette, font families, border radius |
| `web/package.json` | Modify | Add `@fontsource/space-grotesk`, `@fontsource/manrope`, `@fontsource/jetbrains-mono` |

**Design token file** (`tokens.css`):
```css
@layer base {
  :root {
    --primary: #4cd7f6;
    --primary-container: #06b6d4;
    --on-primary: #003640;
    --secondary: #fbabff;
    --secondary-container: #ae05c6;
    --tertiary: #4edea3;
    --tertiary-container: #1bbd85;
    --error: #ffb4ab;
    --error-container: #93000a;
    --surface: #0f131f;
    --surface-dim: #0a0e1a;
    --surface-container-lowest: #0a0e1a;
    --surface-container-low: #171b28;
    --surface-container: #1b1f2c;
    --surface-container-high: #262a37;
    --surface-container-highest: #313442;
    --on-surface: #dfe2f3;
    --on-surface-variant: #bcc9cd;
    --outline: #869397;
    --outline-variant: #3d494c;
  }
}
```

### 1.2 Global Shell

**Files to create/modify**:

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/shell/Header.tsx` | Create | Top navigation bar with logo, nav links, notifications, user avatar |
| `web/src/components/shell/Sidebar.tsx` | Create | Collapsible left sidebar with nav items and status section |
| `web/src/components/shell/StatusFooter.tsx` | Create | Fixed bottom bar with system status and aggregate stats |
| `web/src/components/shell/Shell.tsx` | Create | Composition component wrapping Header + Sidebar + content + footer |
| `web/src/components/shared/Layout.tsx` | Modify | Replace with Shell component |

### 1.3 Live Terminal

The most important new component. Always-visible bottom panel for agent streaming output.

**Files to create**:

| File | Description |
|------|-------------|
| `web/src/components/terminal/LiveTerminal.tsx` | Container with resize handle, collapse toggle, tab bar |
| `web/src/components/terminal/TerminalTab.tsx` | Individual agent output tab with unread badge |
| `web/src/components/terminal/TerminalOutput.tsx` | Auto-scrolling output pane rendering AGENT_STREAM_CHUNK events |
| `web/src/stores/terminal.ts` | Zustand store: active tab, tab list, output buffers, collapsed state |

**Store shape**:
```typescript
interface TerminalStore {
  collapsed: boolean
  height: number // percentage of viewport (default 30)
  activeTab: string | null // agent_id
  tabs: Record<string, {
    agentId: string
    displayName: string
    stage: string
    chunks: string[] // accumulated stream chunks
    unread: number // count since last focus
  }>
  toggleCollapsed: () => void
  setHeight: (h: number) => void
  setActiveTab: (agentId: string) => void
  appendChunk: (agentId: string, chunk: string, stage: string, displayName: string) => void
  markRead: (agentId: string) => void
}
```

**Integration with existing store**: In `pipeline.ts` `handleEvent`, when `AGENT_STREAM_CHUNK` arrives, also call `terminalStore.appendChunk()`.

### 1.4 Enhanced Metrics Bar

**Files to modify**:

| File | Change |
|------|--------|
| `web/src/components/shared/MetricsBar.tsx` | Redesign with segmented progress bar, cost estimate, stage badge, clickable error count |

### 1.5 Keyboard Shortcuts

**File to create**: `web/src/hooks/useKeyboardShortcuts.ts`

Register global shortcuts (W, B, P, A, D, T, backtick, Esc, 1-6, ?).

### 1.6 Tests

| File | Description |
|------|-------------|
| `web/src/__tests__/terminal/LiveTerminal.test.tsx` | Terminal render, tab switching, auto-scroll behavior |
| `web/src/__tests__/terminal/TerminalStore.test.ts` | Store state transitions |
| `web/src/__tests__/shell/Shell.test.tsx` | Layout composition renders correctly |

---

## Phase 2: Event Persistence

**Goal**: Persist pipeline events and conversations to the database so history survives restarts.

### 2.1 Database Models

| File | Action | Description |
|------|--------|-------------|
| `src/colette/db/models.py` | Modify | Add `PipelineEventRecord` and `ConversationMessage` models |

### 2.2 Migration

| File | Action | Description |
|------|--------|-------------|
| `alembic/versions/xxxx_add_event_and_conversation_tables.py` | Create | Alembic migration for new tables |

### 2.3 Event Persister

| File | Action | Description |
|------|--------|-------------|
| `src/colette/orchestrator/event_persister.py` | Create | Async listener that batches events and writes to DB |
| `src/colette/api/app.py` | Modify | Register event persister on startup lifespan |

### 2.4 Conversation Persistence

| File | Action | Description |
|------|--------|-------------|
| `src/colette/api/routes/agents.py` | Modify | Conversation endpoint queries DB for completed runs, in-memory for running |
| `src/colette/db/repositories.py` | Modify | Add `get_conversation_messages(run_id)` and `save_conversation_message()` |

### 2.5 Tests

| File | Description |
|------|-------------|
| `tests/unit/orchestrator/test_event_persister.py` | Batching, flush, skip logic |
| `tests/unit/db/test_event_models.py` | Model creation and queries |
| `tests/unit/api/test_conversation_persistence.py` | Endpoint returns DB data for completed runs |

---

## Phase 3: War Room

**Goal**: Build the spatial stage-room view that replaces the flat board as the default landing.

### 3.1 Components

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/warroom/WarRoom.tsx` | Create | 3x2 grid container for stage rooms |
| `web/src/components/warroom/StageRoom.tsx` | Create | Individual room: header, agents, gate indicator, border state |
| `web/src/components/warroom/AgentChip.tsx` | Create | Agent pill inside room: avatar area + name + state dot + activity |
| `web/src/components/warroom/GateConnector.tsx` | Create | Visual connector between rooms with animation |
| `web/src/components/warroom/FocusedStage.tsx` | Create | Expanded single-stage view (clicking a room) |

### 3.2 View Switcher Update

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/shared/ViewSwitcher.tsx` | Modify | Add "War Room" as first tab (default), rename existing Board |
| `web/src/stores/ui.ts` | Modify | Add `'warroom'` to `activeView` union type |
| `web/src/pages/ProjectDashboard.tsx` | Modify | Render WarRoom when view is 'warroom', make it default |

### 3.3 Animations

| Animation | Implementation |
|-----------|---------------|
| Agent pulse | CSS `@keyframes pulse-cyan` on thinking state |
| Room border glow | Conditional `ring-1 ring-primary/30 glow-cyan` class |
| Gate pass particle | Framer Motion `motion.div` sliding along connector path |
| Room expand | Framer Motion `layout` + `AnimatePresence` |

### 3.4 Tests

| File | Description |
|------|-------------|
| `web/src/__tests__/warroom/WarRoom.test.tsx` | 6 rooms render, correct stage status |
| `web/src/__tests__/warroom/StageRoom.test.tsx` | Agent chips render, gate indicator shows |
| `web/src/__tests__/warroom/AgentChip.test.tsx` | State-based styling |

---

## Phase 4: Operator Intervention

**Goal**: Give the operator full control over the pipeline at any time -- pause, inject feedback, redirect agents, restart or skip stages. Includes the Command Bar UI and all backend endpoints.

### 4.1 Backend: Pipeline Control Endpoints

| File | Action | Description |
|------|--------|-------------|
| `src/colette/api/routes/projects.py` | Modify | Add `POST /pause`, `POST /stages/{stage}/restart`, `POST /stages/{stage}/skip`, `POST /feedback` |
| `src/colette/api/routes/agents.py` | Modify | Add `POST /agents/{agent_id}/message` |
| `src/colette/api/routes/pipelines.py` | Modify | Add `PATCH /handoffs/{stage_name}` |
| `src/colette/api/schemas.py` | Modify | Add request/response schemas: `PauseRequest`, `FeedbackRequest`, `AgentMessageRequest`, `StageRestartRequest`, `StageSkipRequest`, `HandoffPatchRequest` |

### 4.2 Backend: Pipeline Runner Changes

| File | Action | Description |
|------|--------|-------------|
| `src/colette/orchestrator/runner.py` | Modify | Add `pause_project()` method, `_paused` registry, check pause flag before each agent invocation |
| `src/colette/orchestrator/runner.py` | Modify | Add `restart_stage()` -- reset stage state + re-invoke from checkpoint |
| `src/colette/orchestrator/runner.py` | Modify | Add `skip_stage()` -- inject synthetic handoff + advance |
| `src/colette/orchestrator/state.py` | Modify | Add `user_feedback: list[str]`, `paused: bool`, `paused_at: str | None` to `PipelineState` |
| `src/colette/orchestrator/event_bus.py` | Modify | Add 7 new event types: `PIPELINE_PAUSED`, `PIPELINE_RESUMED`, `STAGE_RESTARTED`, `STAGE_SKIPPED`, `OPERATOR_FEEDBACK`, `OPERATOR_MESSAGE`, `HANDOFF_EDITED` |

### 4.3 Backend: Feedback Injection

| File | Action | Description |
|------|--------|-------------|
| `src/colette/stages/*/supervisor.py` | Modify | Read `state['user_feedback']` in supervisor prompt; incorporate operator feedback into agent coordination decisions |
| `src/colette/llm/callbacks.py` | Modify | Add operator message queue; prepend queued messages to next agent LLM call |
| `src/colette/orchestrator/feedback.py` | Create | `OperatorFeedbackManager` -- in-memory queue for per-agent messages, thread-safe |

### 4.4 Frontend: Command Bar

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/command/CommandBar.tsx` | Create | Floating command palette (Ctrl+K trigger), input + suggestion list |
| `web/src/components/command/CommandSuggestion.tsx` | Create | Individual suggestion row with icon, command name, description |
| `web/src/components/command/FeedbackInput.tsx` | Create | Inline quick-feedback input (Ctrl+. trigger) that appears at bottom of active stage |
| `web/src/components/command/SkipStageModal.tsx` | Create | Modal for pasting synthetic handoff when skipping a stage |
| `web/src/components/command/EditHandoffModal.tsx` | Create | JSON editor modal for editing handoff data |
| `web/src/components/command/ConfirmDialog.tsx` | Create | Reusable confirmation dialog for destructive actions (cancel, restart) |
| `web/src/stores/command.ts` | Create | Command bar state: open/closed, input value, filtered suggestions, action dispatch |
| `web/src/hooks/useApi.ts` | Modify | Add API functions: `pausePipeline()`, `resumePipeline()`, `injectFeedback()`, `sendAgentMessage()`, `restartStage()`, `skipStage()`, `editHandoff()` |

### 4.5 Frontend: Persistent Controls

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/shared/MetricsBar.tsx` | Modify | Add Pause/Resume button, Cancel button, Command Bar trigger |
| `web/src/components/warroom/StageRoom.tsx` | Modify | Add context menu (right-click or `...` button) with stage-level actions |
| `web/src/components/warroom/AgentChip.tsx` | Modify | Add context menu with agent-level actions (send message, view output, restart) |
| `web/src/components/board/AgentRow.tsx` | Modify | Add context menu matching War Room agent actions |
| `web/src/types/events.ts` | Modify | Add 7 new intervention event types |
| `web/src/stores/pipeline.ts` | Modify | Handle new event types, add `paused` state |

### 4.6 Frontend: Decision Rail Integration

Operator interventions appear as entries in the Decision Rail (Phase 7). In the interim, they appear in the Activity feed.

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/activity/ActivityEntry.tsx` | Modify | Add rendering for `OPERATOR_FEEDBACK`, `PIPELINE_PAUSED`, `STAGE_RESTARTED`, etc. with distinct "operator" styling (amber icon, "You" label) |

### 4.7 Tests

| File | Description |
|------|-------------|
| `tests/unit/api/test_pause_pipeline.py` | Pause, resume, verify state transitions |
| `tests/unit/api/test_inject_feedback.py` | Feedback delivery, target routing |
| `tests/unit/api/test_restart_stage.py` | Stage restart, state reset, checkpoint replay |
| `tests/unit/api/test_skip_stage.py` | Skip with synthetic handoff |
| `tests/unit/api/test_agent_message.py` | Agent message queuing and delivery |
| `tests/unit/orchestrator/test_feedback_manager.py` | Queue operations, thread safety |
| `web/src/__tests__/command/CommandBar.test.tsx` | Open/close, command routing, suggestion filtering |
| `web/src/__tests__/command/ConfirmDialog.test.tsx` | Confirm/cancel flows |

---

## Phase 5: Tool Visibility

**Goal**: Make tool calls visible and debuggable with the Tool Timeline.

### 5.1 Backend: Enhanced Tool Events

| File | Action | Description |
|------|--------|-------------|
| `src/colette/orchestrator/event_bus.py` | Modify | Add `AGENT_TOOL_RESULT` to `EventType` |
| `src/colette/llm/callbacks.py` | Modify | Include `arguments`, `result_preview`, `duration_ms` in tool call events; emit `AGENT_TOOL_RESULT` on tool end/error |

### 5.2 Frontend: Tool Timeline

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/tools/ToolTimeline.tsx` | Create | Horizontal timeline strip with tool call blocks |
| `web/src/components/tools/ToolBlock.tsx` | Create | Individual tool call: name, duration, status color, hover tooltip |
| `web/src/components/tools/ToolDetail.tsx` | Create | Expandable panel showing full input/output for a tool call |
| `web/src/types/events.ts` | Modify | Add `AGENT_TOOL_RESULT` event type, `ToolCall` interface |
| `web/src/stores/pipeline.ts` | Modify | Track tool calls per agent: `agentTools: Record<string, ToolCall[]>` |

### 5.3 Board Enhancement

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/board/AgentRow.tsx` | Modify | Add tool call count/name cell |
| `web/src/components/board/ToolCell.tsx` | Create | Shows last tool + count, click expands timeline |

### 6.4 Tests

| File | Description |
|------|-------------|
| `tests/unit/llm/test_callbacks_tool_events.py` | Enhanced tool event payloads |
| `web/src/__tests__/tools/ToolTimeline.test.tsx` | Timeline renders blocks in order |
| `web/src/__tests__/tools/ToolBlock.test.tsx` | Status colors, hover shows args |

---

## Phase 6: Artifact Workshop

**Goal**: Replace the flat file list with a live code workbench.

### 6.1 Backend: Artifact Events

| File | Action | Description |
|------|--------|-------------|
| `src/colette/orchestrator/event_bus.py` | Modify | Add `ARTIFACT_GENERATED` to `EventType` |
| `src/colette/stages/implementation/supervisor.py` | Modify | Emit `ARTIFACT_GENERATED` when files are produced |
| `src/colette/stages/testing/supervisor.py` | Modify | Same for test files |
| `src/colette/api/routes/artifacts.py` | Modify | Add `GET /artifacts/{id}/content` endpoint |
| `src/colette/db/models.py` | Modify | Add `content`, `stage`, `agent` columns to `Artifact` |

### 6.2 Frontend: Artifact Workshop

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/artifacts/ArtifactWorkshop.tsx` | Create | Three-panel layout (tree + preview + metadata) |
| `web/src/components/artifacts/FileTree.tsx` | Create | Hierarchical file tree grouped by stage |
| `web/src/components/artifacts/CodePreview.tsx` | Create | Syntax-highlighted code viewer (Shiki integration) |
| `web/src/components/artifacts/FileMetadata.tsx` | Create | Author, stage, size, timestamps, download button |
| `web/src/components/artifacts/DiffView.tsx` | Create | Side-by-side or inline diff when file modified across stages |
| `web/src/stores/artifacts.ts` | Create | File tree state, open tabs, selected file, streaming content |
| `web/src/types/events.ts` | Modify | Add `ARTIFACT_GENERATED` event type |

### 6.3 Shiki Integration

Install `shiki` for syntax highlighting:
```json
{
  "shiki": "^3.0.0"
}
```

Create a shared highlighter instance that supports Python, TypeScript, JSON, YAML, SQL, Markdown, Dockerfile.

| File | Description |
|------|-------------|
| `web/src/utils/highlighter.ts` | Singleton Shiki highlighter with dark theme |

### 6.4 Tests

| File | Description |
|------|-------------|
| `tests/unit/api/test_artifact_content.py` | Individual artifact content endpoint |
| `web/src/__tests__/artifacts/ArtifactWorkshop.test.tsx` | Three-panel renders |
| `web/src/__tests__/artifacts/FileTree.test.tsx` | Tree navigation, stage grouping |

---

## Phase 7: Decision Rail

**Goal**: Persistent right sidebar showing all gate decisions, approvals, and escalations.

### 7.1 Backend: Approval History

| File | Action | Description |
|------|--------|-------------|
| `src/colette/api/routes/approvals.py` | Modify | Add `status` filter (`all`/`pending`/`approved`/`rejected`) |

### 7.2 Frontend: Decision Rail

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/decisions/DecisionRail.tsx` | Create | Right sidebar, collapsible, chronological entries |
| `web/src/components/decisions/GateEntry.tsx` | Create | Gate pass/fail entry with score, reasons, expand |
| `web/src/components/decisions/ApprovalEntry.tsx` | Create | Approval-needed entry with approve/reject buttons, pulsing |
| `web/src/components/decisions/HandoffEntry.tsx` | Create | Stage handoff marker with summary |
| `web/src/components/decisions/EscalationEntry.tsx` | Create | Agent escalation entry |
| `web/src/stores/decisions.ts` | Create | Decision entries, notification count, rail visibility |
| `web/src/hooks/useNotifications.ts` | Create | Browser Notification API integration for approvals |

### 7.3 Tests

| File | Description |
|------|-------------|
| `web/src/__tests__/decisions/DecisionRail.test.tsx` | Rail renders entries in order |
| `web/src/__tests__/decisions/ApprovalEntry.test.tsx` | Approve/reject actions |

---

## Phase 8: History & Analytics

**Goal**: Run history page, run replay, and cross-project analytics.

### 8.1 Backend: History Endpoints

| File | Action | Description |
|------|--------|-------------|
| `src/colette/api/routes/pipelines.py` | Modify | Add `GET /projects/{id}/runs`, `GET /runs/{id}/stages`, `GET /runs/{id}/events` |
| `src/colette/api/routes/agents.py` | Modify | Add `GET /runs/{id}/agents` |
| `src/colette/api/schemas.py` | Modify | Add all new response schemas |
| `src/colette/db/repositories.py` | Modify | Add repository methods for run history queries |

### 8.2 Frontend: History Pages

| File | Action | Description |
|------|--------|-------------|
| `web/src/pages/RunHistory.tsx` | Create | List of past runs with status, duration, tokens |
| `web/src/pages/RunReplay.tsx` | Create | Timeline scrubber replaying events from a past run |
| `web/src/components/history/RunCard.tsx` | Create | Summary card for a single run |
| `web/src/components/history/RunComparison.tsx` | Create | Side-by-side comparison of two runs |
| `web/src/components/history/TimelineScrubber.tsx` | Create | Playback control for replaying events chronologically |
| `web/src/App.tsx` | Modify | Add routes for `/projects/:id/history` and `/projects/:id/runs/:runId` |

### 8.3 Frontend: Analytics Dashboard

| File | Action | Description |
|------|--------|-------------|
| `web/src/pages/Analytics.tsx` | Create | Cross-project analytics page |
| `web/src/components/analytics/TokenChart.tsx` | Create | Bar chart: tokens by stage |
| `web/src/components/analytics/CostEstimate.tsx` | Create | Cost calculation from tokens * model pricing |
| `web/src/components/analytics/AgentPerformance.tsx` | Create | Table: agent metrics across runs |
| `web/src/components/analytics/TrendChart.tsx` | Create | Line chart: cost/duration trends over runs |

**Chart library**: Use `recharts` (lightweight, React-native, good TypeScript support).

### 8.4 Tests

| File | Description |
|------|-------------|
| `tests/unit/api/test_run_history.py` | Run list, stage details, event history endpoints |
| `tests/unit/api/test_agent_metrics.py` | Agent metrics endpoint |
| `web/src/__tests__/history/RunHistory.test.tsx` | Run list renders |
| `web/src/__tests__/history/TimelineScrubber.test.tsx` | Playback controls |

---

## Dependency Graph

```
Phase 1 (Foundation)
  |
  +-- Phase 2 (Event Persistence)
  |     |
  |     +-- Phase 5 (Tool Visibility)      -- needs enhanced events persisted
  |     |
  |     +-- Phase 8 (History & Analytics)  -- needs persisted events
  |
  +-- Phase 3 (War Room)                   -- needs shell from Phase 1
  |     |
  |     +-- Phase 4 (Operator Intervention) -- needs War Room for stage/agent context menus
  |
  +-- Phase 6 (Artifact Workshop)          -- needs ARTIFACT_GENERATED from Phase 2+ setup
  |
  +-- Phase 7 (Decision Rail)              -- needs shell layout from Phase 1
```

**Parallelizable**: Phases 3, 6, and 7 can proceed in parallel after Phase 1 is complete. Phase 4 (Intervention) builds on Phase 3 (War Room) for the stage/agent context menus but the Command Bar and backend endpoints can start after Phase 1. Phase 5 requires Phase 2 (persisted tool events). Phase 8 requires Phase 2.

---

## New Dependencies to Install

### Frontend (`web/package.json`)

| Package | Version | Purpose |
|---------|---------|---------|
| `@fontsource/space-grotesk` | latest | Headline font |
| `@fontsource/manrope` | latest | Body font |
| `@fontsource/jetbrains-mono` | latest | Monospace font |
| `shiki` | ^3.0 | Syntax highlighting for artifact preview |
| `recharts` | ^2.15 | Charts for analytics dashboard |

### Backend

No new Python dependencies needed. All required packages (`sqlalchemy`, `alembic`, `pydantic`, `structlog`) are already in the project.

---

## Migration Strategy

### Database Migrations

1. **Phase 2 migration**: `pipeline_events` + `conversation_messages` tables
2. **Phase 5 migration**: Add `content`, `stage`, `agent` columns to `artifacts` table

Both are additive (new tables/columns), so no data loss and backward-compatible.

### Frontend Migration

The redesign replaces components incrementally:
- Phase 1 replaces the shell but keeps existing views functional inside it
- Phase 3 adds a new view (War Room) alongside existing Board/Pipeline
- Phase 5 replaces the Artifacts view entirely
- Phase 6 adds a new sidebar alongside existing layout

At no point does an existing working view break -- new components are added, old ones are deprecated only after replacements are validated.

---

## File Count Summary

| Phase | Name | New Files | Modified Files | Total |
|-------|------|-----------|----------------|-------|
| 1 | Foundation | ~12 | ~6 | ~18 |
| 2 | Event Persistence | ~4 | ~5 | ~9 |
| 3 | War Room | ~6 | ~3 | ~9 |
| 4 | Operator Intervention | ~10 | ~8 | ~18 |
| 5 | Tool Visibility | ~5 | ~4 | ~9 |
| 6 | Artifact Workshop | ~8 | ~5 | ~13 |
| 7 | Decision Rail | ~7 | ~2 | ~9 |
| 8 | History & Analytics | ~10 | ~5 | ~15 |
| **Total** | | **~62** | **~38** | **~100** |

---

## Quality Gates per Phase

Before marking a phase complete:

- [ ] All new components render correctly with mock data
- [ ] WebSocket events handled for new event types
- [ ] Unit tests pass with 80%+ coverage on new code
- [ ] No TypeScript errors (`tsc --noEmit`)
- [ ] No lint errors (`ruff check` for Python, `eslint` for frontend)
- [ ] Manual testing: submit a project, verify new UI elements update in real-time
- [ ] Responsive layout verified at xl, lg, md, sm breakpoints
