# Colette Web UI — Implementation Program

> **Spec**: `docs/web-ui-plan.md`
> **Goal**: Build a monday.com-style agent board + pipeline orchestration dashboard for Colette's multi-agent SDLC pipeline. React 19 + Vite + TypeScript + Tailwind CSS v4 + Zustand + Framer Motion.
> **Branch**: `feat/web-ui` from `main`
> **Design previews**: `web/stitch-preview/` (open in browser for reference)

---

## Execution Protocol (EVERY Phase)

**CRITICAL: DO NOT STOP between phases. After completing a phase, IMMEDIATELY proceed to the next phase. Continue executing phases sequentially until ALL phases are complete. Only stop when every phase is done or if a blocking error cannot be resolved.**

```
For each phase:
  1. Read this phase's instructions completely
  2. Read all files listed in "Files to Create" and "Files to Modify"
  3. Implement the changes described
  4. Run the validation command for that phase
     TIMEOUT RULE (applies to ALL commands):
     - Set a 120-second (2 min) hard timeout on every command
     - If the command does NOT finish within 120s → KILL it immediately
     - After killing: read the code that caused the hang, find the root cause
     - FIX the root cause FIRST, then re-run (max 3 retries)
  5. If validation fails:
     a. Read the error output
     b. Fix the failing code
     c. Re-run validation
     d. Repeat until green (max 5 fix attempts per phase)
  6. git add <specific files changed>
  7. git commit -m "<type>: <description>"
  8. git push origin feat/web-ui
  9. IMMEDIATELY proceed to next phase — DO NOT STOP or wait for user input
```

**Commit message types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

---

## Phase 1: Scaffold & Backend Endpoints

**Goal**: Scaffold Vite + React + TS + Tailwind project in `web/`, add 2 backend endpoints, set up proxy.

**Depends on**: Nothing

### 1.1 Scaffold `web/`

```bash
cd web/
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install zustand framer-motion react-router
```

Set up Tailwind v4 in `web/vite.config.ts`:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/projects': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

Set up `web/src/index.css`:
```css
@import "tailwindcss";
```

### 1.2 Add backend endpoints

**Files to Create**: `src/colette/api/routes/agents.py`

Two new GET endpoints that read from existing `AgentPresenceTracker` and `ConversationEntry`:

- `GET /api/v1/projects/{project_id}/agents` — returns `{"agents": [...]}` from `AgentPresenceTracker.get_agents()`
- `GET /api/v1/projects/{project_id}/conversation` — returns `{"entries": [...]}` from `get_conversation()` ring buffer

**Files to Modify**: `src/colette/api/app.py` — register the new router

### 1.3 Type definitions

**Files to Create**: `web/src/types/events.ts`

TypeScript types matching backend Pydantic schemas:
- `AgentState`: `'idle' | 'thinking' | 'tool_use' | 'reviewing' | 'handing_off' | 'done' | 'error'`
- `StageStatus`: `'pending' | 'running' | 'completed' | 'failed'`
- `ModelTier`: `'PLANNING' | 'EXECUTION' | 'VALIDATION' | 'REASONING'`
- `AgentPresence`: `{ agent_id, display_name, stage, state, activity, model, tokens_used, target_agent }`
- `ConversationEntry`: `{ agent_id, display_name, stage, message, timestamp, target_agent }`
- `PipelineEvent`: `{ type: EventType, data: Record<string, unknown>, timestamp: string }`
- `EventType` enum matching backend's 20 event types
- `ApprovalRequest`: `{ id, gate_name, stage, risk_level, reason, score, threshold, requested_at }`
- `StageInfo`: `{ name, status, elapsed_ms, agent_count, active_agents, gate_result }`
- `GateResult`: `{ name, passed, score, reasons, needs_approval }`

**Files to Create**: `web/src/types/board.ts`

Board-specific types:
- `BoardColumn` definition for each column (Agent, Status, Activity, Model, Tokens, Duration, Output)
- `StageGroup` with agents array, stage info, gate result, handoff data

### 1.4 Zustand store

**Files to Create**: `web/src/stores/pipeline.ts`

Zustand store that ingests WebSocket events:
```ts
interface PipelineStore {
  stages: Record<string, StageInfo>
  agents: Record<string, AgentPresence>
  conversation: ConversationEntry[]
  events: PipelineEvent[]        // last 200
  approvals: ApprovalRequest[]
  // Actions
  handleEvent: (event: PipelineEvent) => void
  setInitialState: (agents: AgentPresence[], conversation: ConversationEntry[]) => void
  approveGate: (gateId: string) => Promise<void>
  rejectGate: (gateId: string) => Promise<void>
}
```

**Files to Create**: `web/src/stores/ui.ts`

UI state store:
```ts
interface UIStore {
  activeView: 'board' | 'pipeline' | 'activity' | 'artifacts'
  selectedAgentId: string | null
  expandedStages: Set<string>
  activityFilter: { stage?: string; agent?: string; type?: string }
  setActiveView: (view: string) => void
  selectAgent: (id: string | null) => void
  toggleStage: (stage: string) => void
}
```

### 1.5 WebSocket hook

**Files to Create**: `web/src/hooks/useWebSocket.ts`

Custom hook:
- Connects to `ws://localhost:8000/projects/{id}/ws`
- Auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s)
- On connect: fetch initial state from REST endpoints (`/agents`, `/conversation`)
- On message: parse JSON, call `store.handleEvent()`
- Batches updates at 100ms intervals to prevent excessive re-renders
- Returns `{ connected, reconnecting, error }`

**Files to Create**: `web/src/hooks/useApi.ts`

REST API helper:
- `fetchProjects()` — GET `/api/v1/projects`
- `fetchAgents(projectId)` — GET `/api/v1/projects/{id}/agents`
- `fetchConversation(projectId)` — GET `/api/v1/projects/{id}/conversation`
- `approveGate(gateId)` — POST `/api/v1/approvals/{id}/approve`
- `rejectGate(gateId)` — POST `/api/v1/approvals/{id}/reject`
- `fetchArtifacts(projectId)` — GET `/api/v1/projects/{id}/artifacts`
- `downloadArtifactZip(projectId, stage)` — GET `/api/v1/projects/{id}/artifacts/zip`

### 1.6 App shell + router

**Files to Create**: `web/src/App.tsx`, `web/src/main.tsx`

- `main.tsx`: React 19 root, `<BrowserRouter>`, render `<App />`
- `App.tsx`: Routes — `/` → `<ProjectList />`, `/projects/:id` → `<ProjectDashboard />`

**Files to Create**: `web/src/components/shared/Layout.tsx`

App shell layout:
- Top nav: logo, view switcher tabs, search, settings
- Content area below nav
- Uses Professional Dark color tokens as CSS custom properties

### 1.7 Validate

```bash
cd web && npm run build && cd ..
uv run python -c "from colette.api.routes.agents import router; print('OK')"
```

### 1.8 Commit

```bash
git add web/ src/colette/api/routes/agents.py src/colette/api/app.py
git commit -m "feat: scaffold web UI with Vite + React + TS, add agent endpoints"
git push origin feat/web-ui
```

---

## Phase 2: Agent Board (Main View)

**Goal**: Build the monday.com-style agent board with stage groups, agent rows, status pills, gate footers, handoff rows.

**Depends on**: Phase 1

**Design reference**: Open `web/stitch-preview/agent-board.html` in browser

### 2.1 Shared components

**Files to Create**:
- `web/src/components/shared/StatusBadge.tsx` — color-coded stage status badge (Completed/Running/Pending/Failed)
- `web/src/components/shared/TierBadge.tsx` — model tier badge (PLANNING purple, EXECUTION blue, VALIDATION amber)
- `web/src/components/shared/MetricsBar.tsx` — top metrics strip: progress bar, tokens, elapsed, errors
- `web/src/components/shared/ViewSwitcher.tsx` — Board | Pipeline | Activity | Artifacts tabs with underline active state
- `web/src/components/shared/SearchBar.tsx` — filter agents by name, status, stage
- `web/src/utils/format.ts` — `formatDuration(ms)`, `formatTokens(n)`, `formatTimestamp(iso)`
- `web/src/utils/colors.ts` — `statusColor(state)`, `tierColor(tier)`, `stageStatusColor(status)` mapping to CSS custom properties

### 2.2 Board components

**Files to Create**:
- `web/src/components/board/AgentBoard.tsx` — main board: iterates stages, renders `<StageGroup>` for each, `<HandoffRow>` between completed stages
- `web/src/components/board/StageGroup.tsx` — collapsible group: header with stage name + badge + time, agent table inside, gate footer at bottom. Active stage auto-expanded, completed stages collapsed.
- `web/src/components/board/AgentRow.tsx` — single table row: Agent name (`@` prefix), StatusCell, ActivityCell, ModelCell, TokenCell, DurationCell. Click → opens drawer.
- `web/src/components/board/StatusCell.tsx` — animated status pill per agent state. Uses Framer Motion for transitions: pulse on thinking, spin on tool_use, fade-in on done.
- `web/src/components/board/ActivityCell.tsx` — truncated activity text, expand on hover/click
- `web/src/components/board/ModelCell.tsx` — monospace model string + `<TierBadge>`, optional "fallback" indicator
- `web/src/components/board/TokenCell.tsx` — token count right-aligned + mini progress bar (tokens / budget)
- `web/src/components/board/DurationCell.tsx` — live timer using `requestAnimationFrame`, monospace display
- `web/src/components/board/HandoffRow.tsx` — full-width highlighted row between groups: blue left border, arrow icon, handoff details (stories count, NFRs, score)
- `web/src/components/board/GateFooter.tsx` — gate status bar: gate name, pass/fail/pending indicator, score, [Approve]/[Reject] buttons if needs_approval
- `web/src/components/board/BoardToolbar.tsx` — search/filter bar above the board

### 2.3 Agent timer hook

**Files to Create**: `web/src/hooks/useAgentTimer.ts`

Single `requestAnimationFrame` loop that updates all visible agent duration counters. Avoids N separate intervals.

### 2.4 ProjectDashboard page

**Files to Create**: `web/src/pages/ProjectDashboard.tsx`

- Reads `projectId` from route params
- Initializes WebSocket connection via `useWebSocket(projectId)`
- Renders: `<Layout>` → `<MetricsBar>` → active view (`<AgentBoard>` by default)
- View switching via `<ViewSwitcher>`

### 2.5 ProjectList page

**Files to Create**: `web/src/pages/ProjectList.tsx`

- Fetches projects from REST API
- Renders cards with: name, description, 6-segment progress bar, status badge, active agents, timestamp
- Click card → navigate to `/projects/:id`

### 2.6 Validate

```bash
cd web && npm run build && npm run lint
```

### 2.7 Commit

```bash
git add web/src/
git commit -m "feat: implement agent board with stage groups, status pills, gate footers"
git push origin feat/web-ui
```

---

## Phase 3: Pipeline Orchestration View

**Goal**: Build the bird's-eye pipeline DAG with stage nodes, gate checkpoints, Gantt timeline, summary cards.

**Depends on**: Phase 2

**Design reference**: Open `web/stitch-preview/pipeline-view.html` in browser

### 3.1 Pipeline components

**Files to Create**:
- `web/src/components/pipeline/PipelineView.tsx` — full view: flow diagram + Gantt + summary. Reads stages/gates from store.
- `web/src/components/pipeline/StageNode.tsx` — rounded rect node: stage name, status icon, agent count badge, elapsed time. Click → switch to Board view scrolled to that group.
- `web/src/components/pipeline/GateNode.tsx` — small circle/diamond between stages: pass (green checkmark + score), fail (red X + tooltip), pending (grey), needs_approval (pulsing + inline buttons).
- `web/src/components/pipeline/FlowConnector.tsx` — horizontal line/arrow between nodes. Green for passed, blue animated for active, grey dashed for pending. CSS only (no SVG).
- `web/src/components/pipeline/GanttTimeline.tsx` — horizontal bars per stage: completed = green solid, running = blue with animated width growth, pending = grey dashed. Each bar shows stage name + duration.
- `web/src/components/pipeline/SummaryCards.tsx` — row of metric cards: total tokens, elapsed, agents active/total, errors, current stage.

### 3.2 Wire into dashboard

**Files to Modify**: `web/src/pages/ProjectDashboard.tsx` — add `<PipelineView>` as view option when `activeView === 'pipeline'`

### 3.3 Validate

```bash
cd web && npm run build && npm run lint
```

### 3.4 Commit

```bash
git add web/src/components/pipeline/ web/src/pages/ProjectDashboard.tsx
git commit -m "feat: add pipeline orchestration view with DAG, Gantt, summary"
git push origin feat/web-ui
```

---

## Phase 4: Agent Detail Drawer & Activity Feed

**Goal**: Build the agent detail drawer (slides from right) and chronological activity feed.

**Depends on**: Phase 2

### 4.1 Agent drawer

**Files to Create**:
- `web/src/components/detail/AgentDrawer.tsx` — right-side slide-in panel (Framer Motion `animate={{ x: 0 }}`). Header: avatar, name, stage, status pill, model+tier. Stats row: tokens/budget, duration, messages. Tabs: Output | Tools | History. Close button.
- `web/src/components/detail/LiveOutput.tsx` — monospace text area showing streaming LLM output from `AGENT_STREAM_CHUNK` events. Auto-scroll to bottom. Dark bg (#0d1117).
- `web/src/components/detail/ToolCallLog.tsx` — list of tool invocations: tool name, args preview (truncated), result badge (Success green / Running blue / Error red).
- `web/src/components/detail/AgentConversation.tsx` — filtered conversation entries for the selected agent only.

### 4.2 Activity feed

**Files to Create**:
- `web/src/components/activity/ActivityFeed.tsx` — chronological feed of all events. Filter bar at top (pills: All, Messages, Handoffs, Gates, Approvals). Auto-scroll with "N new updates" sticky indicator.
- `web/src/components/activity/ActivityEntry.tsx` — single entry: agent avatar circle + name + timestamp + message. Variant styles: normal message, handoff (blue left border), gate result (green/red left border), approval request (purple border + action buttons).
- `web/src/components/activity/ActivityFilter.tsx` — filter by stage, agent, event type. Pill-style toggle buttons.

### 4.3 Wire into dashboard

**Files to Modify**: `web/src/pages/ProjectDashboard.tsx` — render `<AgentDrawer>` when `selectedAgentId` is set. Render `<ActivityFeed>` when `activeView === 'activity'`.

### 4.4 Validate

```bash
cd web && npm run build && npm run lint
```

### 4.5 Commit

```bash
git add web/src/components/detail/ web/src/components/activity/ web/src/pages/ProjectDashboard.tsx
git commit -m "feat: add agent detail drawer and activity feed"
git push origin feat/web-ui
```

---

## Phase 5: Artifacts & Approvals

**Goal**: Build artifact browser and approval queue panels.

**Depends on**: Phase 2

### 5.1 Artifacts panel

**Files to Create**:
- `web/src/components/artifacts/ArtifactPanel.tsx` — tree view grouped by stage → file type. Search/filter by name. Download buttons (individual + zip per stage).
- `web/src/components/artifacts/FilePreview.tsx` — syntax-highlighted code preview (use `<pre><code>` with CSS classes) or rendered markdown. Lazy-load content on click.

### 5.2 Approval queue

**Files to Create**:
- `web/src/components/approvals/ApprovalQueue.tsx` — list of pending approvals with badge count. History of past decisions below.
- `web/src/components/approvals/ApprovalCard.tsx` — single approval: gate name, stage, risk level badge, reason, score vs threshold, [Approve] / [Reject] buttons with optional comment input. Expandable context section.

### 5.3 Wire into dashboard

**Files to Modify**: `web/src/pages/ProjectDashboard.tsx` — render `<ArtifactPanel>` when `activeView === 'artifacts'`. Show approval badge count on nav tab.

### 5.4 Validate

```bash
cd web && npm run build && npm run lint
```

### 5.5 Commit

```bash
git add web/src/components/artifacts/ web/src/components/approvals/ web/src/pages/ProjectDashboard.tsx
git commit -m "feat: add artifact browser and approval queue panels"
git push origin feat/web-ui
```

---

## Phase 6: Polish & Integration

**Goal**: Keyboard shortcuts, responsive layout, dark mode tokens, Makefile commands, final build.

**Depends on**: All previous phases

### 6.1 Keyboard shortcuts

**Files to Modify**: `web/src/App.tsx` or `web/src/pages/ProjectDashboard.tsx`

Global key listeners:
- `B` → Board view, `P` → Pipeline, `A` → Activity, `F` → Artifacts
- `1-6` → jump to stage group (expand + scroll)
- `Escape` → close drawer

### 6.2 Responsive breakpoints

**Files to Modify**: All board components

| Breakpoint | Change |
|---|---|
| >= 1440px | Full board, all columns, drawer side-by-side |
| 1024-1439px | Hide Duration + Output columns, drawer overlays |
| 768-1023px | Agent + Status + Activity only, stacked groups, drawer full-width |
| < 768px | Card view per agent, swipe between stages |

Use Tailwind responsive prefixes (`lg:`, `md:`, `sm:`).

### 6.3 CSS custom properties

**Files to Modify**: `web/src/index.css`

Add Professional Dark design tokens as CSS custom properties:
```css
:root {
  --bg-primary: #0d1117;
  --bg-surface: #161b22;
  --bg-surface-2: #21262d;
  --bg-hover: rgba(47, 129, 247, 0.04);
  --border: #30363d;
  --text-primary: #e6edf3;
  --text-secondary: #7d8590;
  --accent: #2f81f7;
  --green: #3fb950;
  --red: #f85149;
  --amber: #d29922;
  --purple: #a371f7;
}
```

### 6.4 Makefile commands

**Files to Modify**: `Makefile`

```makefile
web:              ## Build web UI for production
	cd web && npm run build

web-dev:          ## Start web UI dev server
	cd web && npm run dev

web-install:      ## Install web UI dependencies
	cd web && npm install
```

### 6.5 Motion guidelines

All Framer Motion animations:
- Transitions: 200-300ms ease-out
- Status pill changes: 400ms color morph
- Stage completion: green flash on header, auto-collapse after 1s
- New activity entries: slide from bottom, 200ms
- Agent drawer: slide from right, 250ms ease-out
- View switches: crossfade 150ms
- Respect `prefers-reduced-motion`: `useReducedMotion()` from Framer Motion

### 6.6 Final validation

```bash
cd web && npm run build && npm run lint
make check  # Backend still passes
```

### 6.7 Commit

```bash
git add web/ Makefile
git commit -m "feat: polish web UI — shortcuts, responsive, dark theme, make commands"
git push origin feat/web-ui
```

---

## Phase 7: Backend Tests for New Endpoints

**Goal**: Add tests for the 2 new agent endpoints. Ensure `make check` passes.

**Depends on**: Phase 1

### 7.1 Tests

**Files to Create**: `tests/unit/api/test_agents_routes.py`

- Test `GET /api/v1/projects/{id}/agents` returns agent list
- Test `GET /api/v1/projects/{id}/conversation` returns conversation entries
- Test 404 for non-existent project
- Mock `AgentPresenceTracker` and conversation ring buffer

### 7.2 Validate

```bash
make check  # lint + typecheck + test-unit + security
```

### 7.3 Commit

```bash
git add tests/unit/api/test_agents_routes.py
git commit -m "test: add unit tests for agent presence and conversation endpoints"
git push origin feat/web-ui
```

---

## Dependency Graph

```
Phase 1 (scaffold + endpoints)
  ├── Phase 2 (agent board)  ───┐
  │     ├── Phase 3 (pipeline)  │
  │     ├── Phase 4 (drawer + feed)
  │     └── Phase 5 (artifacts + approvals)
  └── Phase 7 (backend tests)   │
                                 │
  Phase 2-5 ─────────────────── Phase 6 (polish)
```

Recommended serial order:
```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
```
