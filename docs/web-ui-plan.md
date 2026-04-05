# Colette Web UI — "Agent Board"

## Requirements

Build a web dashboard inspired by monday.com's work management UI, but purpose-built for managing AI agents instead of people. The dashboard provides real-time visibility into Colette's multi-agent pipeline through two complementary views: a **Board View** (agent-centric table grouped by stage) and a **Pipeline View** (orchestration flow with gates). The UI must:

- Show a monday.com-style board where agents are rows grouped by pipeline stage
- Each agent row displays: status, model, tokens, current activity, duration, and output
- Provide a top-level pipeline orchestration view showing the 6-stage DAG with quality gates
- Support real-time updates via WebSocket (status transitions, token counts, activity descriptions)
- Show inter-agent handoffs as highlighted transitions between groups
- Include approval workflows inline (approve/reject directly from the board)
- Browse and download artifacts per stage via a sidebar drawer
- Work alongside the CLI (connects to the same FastAPI backend via WebSocket)

## What Already Exists (No New Backend Work Needed)

| Backend Component | Status |
|---|---|
| WebSocket endpoint (`/projects/{id}/ws`) | Done — streams all event types |
| SSE endpoint (`/projects/{id}/pipeline/events`) | Done — with catch-up |
| `AgentPresenceTracker` with 7 states | Done — IDLE/THINKING/TOOL_USE/REVIEWING/HANDING_OFF/DONE/ERROR |
| `ConversationEntry` ring buffer | Done — 50-entry bounded |
| 20 event types (`EventType` enum) | Done — AGENT_STARTED through PIPELINE_COMPLETED |
| Projects CRUD + list | Done |
| Approvals list/approve/reject | Done |
| Artifacts list + zip download | Done |
| CORS middleware | Done — configurable origins |

**The backend is feature-complete for this UI.** We only need to add 2 small endpoints (agent presence snapshot + conversation history) and build the frontend.

## Tech Stack

| Choice | Why |
|---|---|
| **React 19 + Vite** | Lightweight, no SSR needed (FastAPI is the server) |
| **TypeScript** | Type safety matching backend Pydantic models |
| **Tailwind CSS v4** | Rapid styling, dark mode |
| **Zustand** | Minimal state management for WebSocket-driven state |
| **Framer Motion** | Smooth agent animations (typing indicators, transitions) |
| **React Router v7** | SPA routing (project list -> project detail) |

Frontend lives at `web/` in the repo root, served by Vite dev server (proxying API to FastAPI on port 8000).

## Implementation Phases

### Phase 1: Scaffold & WebSocket Connection

**Files:** `web/` scaffold, `src/colette/api/routes/agents.py`

1. Scaffold Vite + React + TS + Tailwind project in `web/`
2. Add 2 backend endpoints:
   - `GET /api/v1/projects/{id}/agents` — returns current `AgentPresenceTracker.get_agents()` snapshot
   - `GET /api/v1/projects/{id}/conversation` — returns `get_conversation()` ring buffer
3. Build `useWebSocket` hook that connects to `ws://localhost:8000/projects/{id}/ws`
4. Build Zustand store that ingests WebSocket events and maintains:
   - `stages: Record<string, StageStatus>`
   - `agents: Record<string, AgentPresence>`
   - `conversation: ConversationEntry[]`
   - `events: PipelineEvent[]` (last 200)
   - `approvals: ApprovalRequest[]`
5. Type definitions matching backend schemas

### Phase 2: Agent Board — The Main View (monday.com-style)

**Key component:** `<AgentBoard />`

The primary interface. A table where agents are rows, grouped by pipeline stage (like monday.com groups items by status/sprint). Each group is collapsible.

1. **Group headers** (one per stage): stage name, status badge, stage progress %, gate result, elapsed time. The active stage group is expanded by default, completed stages are collapsed.
2. **Agent rows** — each row is one agent with these columns:

   | Column | Content | Style |
   |---|---|---|
   | **Agent** | Avatar + name (e.g. `@Backend Dev`) | Left-pinned, bold |
   | **Status** | Color-coded pill: Idle / Thinking / Tool Use / Reviewing / Handing Off / Done / Error | monday.com-style colored labels |
   | **Activity** | Current task description, live-updates (e.g. "Implementing auth service...") | Truncated, expand on hover |
   | **Model** | Model string + tier badge (e.g. `claude-sonnet-4-6` `EXECUTION`) | Monospace, tier color-coded |
   | **Tokens** | Token count with mini progress bar against budget | Right-aligned numeric |
   | **Duration** | Time since agent started, live counter | Monospace |
   | **Output** | Click to expand: live LLM stream or last output preview | Icon button → drawer |

3. **Row interactions:**
   - Click row → opens agent detail drawer (right side)
   - Hover row → subtle highlight, shows "View Output" action
   - Status column animates on transition (pulse on thinking, spin on tool_use)

4. **Group footer** per stage: quality gate status bar showing gate name, pass/fail, reasons on hover, approve/reject buttons if approval pending

5. **Handoff rows:** Between groups, a special highlighted row shows the handoff event (e.g. "Requirements → Design handoff | 12 user stories, 5 NFRs, completeness: 92%") with a connecting arrow visual

### Phase 3: Pipeline Orchestration View

**Key component:** `<PipelineView />`

A dedicated view (tab in the top nav) showing the full orchestration DAG — the "bird's eye" of the pipeline.

1. **Horizontal flow diagram:** 6 stage nodes connected by arrows, with gate checkpoints between each pair
2. **Stage nodes** show:
   - Stage name + status icon
   - Mini agent count badge (e.g. "3/3 done" or "2 active")
   - Elapsed time
   - Click to jump to that group in the Board View
3. **Gate nodes** between stages show:
   - Gate name
   - Pass/fail/pending indicator
   - Completeness score (e.g. "87%")
   - If failed: red with reasons tooltip
   - If pending approval: pulsing magenta with approve/reject inline
4. **Active stage highlight:** The currently running stage node has a glowing border and animated connector showing data flowing to it
5. **Progress timeline** below the flow: Gantt-style horizontal bars per stage showing start/end/duration, stacked vertically. Completed = green, running = cyan animated, pending = grey dashed
6. **Summary cards** below the Gantt:
   - Total tokens across all stages
   - Total elapsed time
   - Error count
   - Agents active / total
   - Current stage + ETA (if estimable)

### Phase 4: Agent Detail Drawer & Activity Feed

**Key components:** `<AgentDrawer />`, `<ActivityFeed />`

1. **Agent detail drawer** (slides in from right when agent row clicked):
   - Header: avatar, name, stage, status pill, model + tier
   - **Stats row:** tokens used/budget, duration, messages sent
   - **Live output panel:** streaming LLM text (`AGENT_STREAM_CHUNK` events), monospace, auto-scroll
   - **Tool calls log:** list of tool invocations with name, args preview, result status
   - **Conversation history:** all messages from this agent
   - Close button returns to board

2. **Activity feed** (bottom panel or right sidebar tab):
   - Chronological feed of all agent messages, handoffs, gate results, approvals — similar to monday.com's Updates section
   - Each entry: agent avatar + name + timestamp + message
   - Handoff entries highlighted with cyan bar
   - Gate results highlighted with green/red bar
   - Approval requests highlighted with magenta bar + action buttons
   - Filter by: stage, agent, event type
   - Auto-scroll with "N new updates" sticky indicator

### Phase 5: Artifacts & Approvals Panels

**Key components:** `<ArtifactPanel />`, `<ApprovalQueue />`

1. **Artifact panel** (sidebar tab or dedicated view):
   - Tree view grouped by stage → file type
   - File preview with syntax highlighting (code) or rendered markdown
   - Download individual files or full stage zip
   - Search/filter artifacts by name

2. **Approval queue** (badge count in top nav, inline in board + dedicated view):
   - monday.com-style list of pending approvals
   - Each shows: gate name, stage, risk level, reason, requested time
   - Context expandable: shows what the gate evaluated, scores, thresholds
   - Approve / Reject buttons with optional comment
   - History of past approvals with decisions and who approved

### Phase 6: Polish & Integration

1. **View switcher** in top nav: Board | Pipeline | Activity | Artifacts
2. Dark/light mode toggle
3. Responsive layout (desktop-first, functional on tablet)
4. Keyboard shortcuts: `B` board, `P` pipeline, `A` activity, `1-6` jump to stage group
5. Sound effects toggle (subtle notifications for stage completion, errors, approvals)
6. Add `make web` / `make web-dev` commands to Makefile
7. Proxy config so `web/` dev server forwards `/api/` to FastAPI
8. Production build: `web/dist/` served as static files by FastAPI (optional)
9. Search/filter bar: filter agents by name, status, stage, model

## Component Architecture

```
web/src/
  main.tsx
  App.tsx                        # Router + view switcher
  stores/
    pipeline.ts                  # Zustand store (WebSocket -> state)
    ui.ts                        # UI state (active view, selected agent, expanded groups)
  hooks/
    useWebSocket.ts              # WS connection + reconnect
    useApi.ts                    # REST API calls
    useAgentTimer.ts             # Live duration counters per agent
  types/
    events.ts                    # TypeScript types matching backend
    board.ts                     # Board column definitions, group types
  pages/
    ProjectList.tsx              # List all projects (cards with status summary)
    ProjectDashboard.tsx         # Top-level layout: nav + active view
  components/
    board/                       # monday.com-style agent board
      AgentBoard.tsx             # Main board: groups + rows + columns
      StageGroup.tsx             # Collapsible stage group header + agent rows
      AgentRow.tsx               # Single agent row with all columns
      StatusCell.tsx             # Color-coded status pill (animated)
      ActivityCell.tsx           # Truncated activity with expand
      ModelCell.tsx              # Model string + tier badge
      TokenCell.tsx              # Token count + mini bar
      DurationCell.tsx           # Live timer
      HandoffRow.tsx             # Highlighted handoff between groups
      GateFooter.tsx             # Gate status bar at group bottom
      BoardToolbar.tsx           # Search, filter, view options
    pipeline/                    # Orchestration flow view
      PipelineView.tsx           # Full DAG visualization
      StageNode.tsx              # Stage node in the flow
      GateNode.tsx               # Gate checkpoint between stages
      FlowConnector.tsx          # Animated arrows between nodes
      GanttTimeline.tsx          # Horizontal Gantt bars per stage
      SummaryCards.tsx            # Aggregate metrics row
    detail/                      # Agent detail drawer
      AgentDrawer.tsx            # Right-side slide-in panel
      LiveOutput.tsx             # Streaming LLM text
      ToolCallLog.tsx            # Tool invocations list
      AgentConversation.tsx      # Agent-specific message history
    activity/                    # Activity feed
      ActivityFeed.tsx           # Chronological all-agent feed
      ActivityEntry.tsx          # Single feed entry (message/handoff/gate)
      ActivityFilter.tsx         # Filter by stage, agent, type
    artifacts/
      ArtifactPanel.tsx          # File tree + preview
      FilePreview.tsx            # Syntax-highlighted code / markdown
    approvals/
      ApprovalQueue.tsx          # Pending approvals list
      ApprovalCard.tsx           # Single approval with context + actions
    shared/
      StatusBadge.tsx            # Reusable status indicator
      TierBadge.tsx              # Model tier color badge
      MetricsBar.tsx             # Top metrics strip
      ViewSwitcher.tsx           # Board | Pipeline | Activity | Artifacts tabs
      Layout.tsx                 # App shell with nav
      SearchBar.tsx              # Global search/filter
  utils/
    format.ts                    # Time formatting, number formatting
    colors.ts                    # Status -> color mapping
```

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| WebSocket disconnects during long runs | MEDIUM | Auto-reconnect with catch-up events (backend already supports this) |
| Large artifact content in memory | LOW | Lazy-load file content only on preview click |
| Agent presence not exposed via REST yet | LOW | Add 2 simple endpoints in Phase 1 |
| Board re-renders on every WS event | MEDIUM | Zustand selectors + React.memo on rows, batch WS updates at 100ms intervals |
| Pipeline view SVG complexity | LOW | Use simple CSS flexbox layout instead of full SVG; only animate active connections |
| Many concurrent agent timers | LOW | Single `requestAnimationFrame` loop updating all visible timers |

## Visual Design

### Design Direction: Professional Dark

Clean, tool-grade dark UI inspired by Linear and GitHub Dark. No glow effects, no neon — just clear hierarchy, readable data, and subtle color accents for status. The aesthetic is a professional work management tool, not a sci-fi dashboard.

### Color Palette

| Token | Value | Usage |
|---|---|---|
| `--bg-primary` | `#0d1117` | Page background |
| `--bg-surface` | `#161b22` | Cards, panels, stage groups |
| `--bg-surface-2` | `#21262d` | Nested surfaces, table headers |
| `--bg-hover` | `rgba(47, 129, 247, 0.04)` | Row/item hover states |
| `--border` | `#30363d` | Panel borders, dividers |
| `--text-primary` | `#e6edf3` | Headings, primary text |
| `--text-secondary` | `#7d8590` | Labels, timestamps, muted text |
| `--accent` | `#2f81f7` | Primary accent — running states, active tabs, links |
| `--green` | `#3fb950` | Completed, passed gates, done status |
| `--red` | `#f85149` | Errors, failed gates |
| `--amber` | `#d29922` | Warnings, pending states, reviewing |
| `--purple` | `#a371f7` | Tool use status, secondary accent |

### Typography

| Element | Font | Size |
|---|---|---|
| Headings | Inter 600-700 | `clamp(1.25rem, 3vw, 2rem)` |
| Body / UI | Inter 400-500 | `clamp(0.8rem, 1.2vw, 1rem)` |
| Code / Monospace | JetBrains Mono | `clamp(0.7rem, 1vw, 0.875rem)` |
| Agent names | Inter 600 | `0.875rem` |
| Timestamps | JetBrains Mono 400 | `0.75rem` |

### Layout Specifications

#### Main Dashboard (ProjectDashboard) — Board View

```
+-----------------------------------------------------------------------+
| COLETTE    [Board] [Pipeline] [Activity] [Artifacts]    [Search] [⚙]  |
+-----------------------------------------------------------------------+
| MetricsBar                                                            |
| [▓▓▓▓▓▓▓░░░░░░ 45%] Tokens: 42,847  Elapsed: 3m12s  Errors: 0       |
+-----------------------------------------------------------------------+
| ┌─────────────────────────────────────────────────────────────────┐   |
| │ ▼ REQUIREMENTS                          COMPLETED ✓   1m 04s   │   |
| ├─────────┬──────────┬─────────────────┬──────────┬───────┬──────┤   |
| │ Agent   │ Status   │ Activity        │ Model    │ Tokens│ Time │   |
| ├─────────┼──────────┼─────────────────┼──────────┼───────┼──────┤   |
| │ @Researcher │ Done ✓ │ Completed analysis │ claude.. │ 1.2k │ 32s │   |
| │ @Analyst    │ Done ✓ │ 12 user stories    │ claude.. │ 980  │ 28s │   |
| ├─────────────┴────────┴─────────────────┴──────────┴───────┴──────┤   |
| │ Gate: Requirements Gate  ✓ PASSED  Score: 92%                    │   |
| └──────────────────────────────────────────────────────────────────┘   |
| ┌── ⟹ Handoff: Requirements → Design  |  12 stories, 5 NFRs ─────┐   |
| └──────────────────────────────────────────────────────────────────┘   |
| ┌─────────────────────────────────────────────────────────────────┐   |
| │ ▼ DESIGN                                COMPLETED ✓   1m 22s   │   |
| ├─────────┬──────────┬─────────────────┬──────────┬───────┬──────┤   |
| │ @Architect   │ Done ✓ │ System arch done   │ claude.. │ 2.1k │ 45s │   |
| │ @API Designer│ Done ✓ │ OpenAPI spec done  │ claude.. │ 1.8k │ 37s │   |
| │ @UI Designer │ Done ✓ │ Wireframes done    │ claude.. │ 1.4k │ 31s │   |
| ├──────────────┴────────┴─────────────────┴──────────┴───────┴──────┤   |
| │ Gate: Design Gate  ✓ PASSED  Score: 88%                          │   |
| └──────────────────────────────────────────────────────────────────┘   |
| ┌─────────────────────────────────────────────────────────────────┐   |
| │ ▼ IMPLEMENTATION                     ● RUNNING       0m 46s    │   |
| ├─────────┬──────────┬─────────────────┬──────────┬───────┬──────┤   |
| │ @Backend Dev │ ● Thinking │ Implementing auth...│ claude.. │ 840 │ 22s │   |
| │ @Frontend Dev│ ⚙ Tool Use│ Running npm build   │ claude.. │ 620 │ 18s │   |
| │ @Database Dev│ ○ Idle     │ Waiting...          │ claude.. │ 0   │ --  │   |
| │ @Verifier    │ ○ Idle     │ Waiting...          │ claude.. │ 0   │ --  │   |
| │ @Refactor    │ ○ Idle     │ Waiting...          │ claude.. │ 0   │ --  │   |
| │ @Test Agent  │ ○ Idle     │ Waiting...          │ claude.. │ 0   │ --  │   |
| └──────────────────────────────────────────────────────────────────┘   |
| ┌─────────────────────────────────────────────────────────────────┐   |
| │ ▷ TESTING                               ○ PENDING              │   |
| │ ▷ DEPLOYMENT                            ○ PENDING              │   |
| │ ▷ MONITORING                            ○ PENDING              │   |
| └──────────────────────────────────────────────────────────────────┘   |
+-----------------------------------------------------------------------+
|                    AgentDrawer (slides from right when row clicked)    |
+-----------------------------------------------------------------------+
```

#### Pipeline Orchestration View

```
+-----------------------------------------------------------------------+
| COLETTE    [Board] [Pipeline] [Activity] [Artifacts]    [Search] [⚙]  |
+-----------------------------------------------------------------------+
|                                                                        |
|   [Requirements] ──✓── [Design] ──✓── [Implementation] ──○── [Testing]|
|      ✓ Done         ✓ Done       ● Running  2/6 active    ○ Pending   |
|      1m04s          1m22s        0m46s                                 |
|                                                                        |
|                       [Deployment] ──○── [Monitoring]                  |
|                         ○ Pending         ○ Pending                    |
|                                                                        |
+-----------------------------------------------------------------------+
| Gantt Timeline                                                         |
| Requirements  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  1m04s           |
| Design        ░░░░░░░░████████████░░░░░░░░░░░░░░░░░  1m22s           |
| Implementation░░░░░░░░░░░░░░░░░░░░█████▓▓▓            0m46s...       |
| Testing       ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  --             |
| Deployment    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  --             |
| Monitoring    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  --             |
+-----------------------------------------------------------------------+
| Summary                                                                |
| [Tokens: 42,847] [Elapsed: 3m12s] [Agents: 2/20 active] [Errors: 0] |
+-----------------------------------------------------------------------+
```

### Agent Status Pills (monday.com-style)

Color-coded status labels displayed in the Status column of each agent row. Each pill has a background color, icon, and optional animation.

| State | Label | Color | Icon | Animation |
|---|---|---|---|---|
| IDLE | `Idle` | `#7d8590` muted | `○` hollow circle | None, static |
| THINKING | `Thinking` | `#2f81f7` blue | `●` filled circle | Pulsing opacity, 1.5s ease |
| TOOL_USE | `Tool Use` | `#a371f7` purple | `⚙` gear | Rotating 360deg, 1.5s |
| REVIEWING | `Reviewing` | `#d29922` amber | `🔍` magnifier | Subtle pulse, 1.5s |
| HANDING_OFF | `Handing Off` | `#2f81f7` blue | `→` arrow | Slide-right animation |
| DONE | `Done` | `#3fb950` green | `✓` checkmark | Fade-in, 200ms |
| ERROR | `Error` | `#f85149` red | `✕` cross | Flash twice, then static |

### Handoff Row Design

Between stage groups, a highlighted row spans all columns showing the handoff:

```
+-----------------------------------------------------------------------+
│ ⟹  Requirements → Design   │ 12 user stories │ 5 NFRs │ Score: 92%  │
+-----------------------------------------------------------------------+
```

Styled with: blue left border (`--accent`), subtle blue-tinted background, bold font, connecting arrow icon.

### Gate Footer Design

At the bottom of each stage group, a status bar shows the quality gate result:

```
+-----------------------------------------------------------------------+
│ Gate: Requirements Gate    ✓ PASSED    Score: 92%    [View Details]   │
+-----------------------------------------------------------------------+
```

| Gate State | Style |
|---|---|
| Pending | Grey dashed border, "Pending" text |
| Evaluating | Amber pulsing border, spinner icon |
| Passed | Green solid border, checkmark, score |
| Failed | Red solid border, X icon, reasons expandable |
| Needs Approval | Purple pulsing border, [Approve] [Reject] buttons inline |

### Activity Feed Entry Types

```
+------------------------------------------+
| Activity                             [v] |
+------------------------------------------+
|                                          |
| ● @Researcher                  2:31:04  |
| Analyzing project requirements for       |
| e-commerce platform...                   |
|                                          |
| ● @Analyst                     2:31:12  |
| Identified 12 user stories from the      |
| project description.                     |
|                                          |
| ⟹ Handoff: Requirements → Design        |
| [blue bar] 12 stories, 5 NFRs, 92%      |
|                                          |
| ✓ Gate: Requirements Gate PASSED         |
| [green bar] Score: 92%                   |
|                                          |
| ● @Architect                   2:32:01  |
| Received requirements handoff.           |
| Beginning system architecture...         |
|                                          |
| ⚠ Approval Required                     |
| [purple bar] Design Gate — T1 High risk  |
| [Approve] [Reject] [View Details]        |
|                                          |
+------------------------------------------+
```

### Approval Queue Design (monday.com-style list)

```
+------------------------------------------+
| Pending Approvals                    (2) |
+------------------------------------------+
| ◉ DESIGN GATE — T1 High        2:33:15  |
|   Risk: Architecture uses unfamiliar     |
|   stack for this team                    |
|   Score: 78% (threshold: 85%)            |
|   [Approve ✓]  [Reject ✕]  [Details ▸]  |
+------------------------------------------+
| ◉ IMPL GATE — T2 Medium        2:38:44  |
|   Risk: Test coverage at 72%             |
|   Score: 72% (threshold: 80%)            |
|   [Approve ✓]  [Reject ✕]  [Details ▸]  |
+------------------------------------------+
```

### Responsive Breakpoints

| Breakpoint | Layout Change |
|---|---|
| >= 1440px | Full board with all columns visible, drawer side-by-side |
| 1024-1439px | Board hides Duration + Output columns, drawer overlays |
| 768-1023px | Board shows Agent + Status + Activity only, stacked groups, drawer full-width |
| < 768px | Card view (each agent as a card instead of row), swipe between stages |

### Motion Guidelines

- All transitions 200-300ms ease-out
- Status pill changes animate over 400ms (color morph + icon swap)
- Stage group completion: green flash on group header, auto-collapse after 1s
- New activity entries: slide in from bottom, 200ms
- Agent drawer: slide from right, 250ms ease-out
- Pipeline view node transitions: 300ms with easing
- Gantt bar growth: animated width increase for running stages
- Handoff rows: slide-in with cyan pulse on appearance
- View switches: crossfade 150ms
- Respect `prefers-reduced-motion`: disable all loops, keep functional transitions at 200ms max

## Backend Additions (Phase 1)

Two new endpoints in `src/colette/api/routes/agents.py`:

### GET /api/v1/projects/{project_id}/agents

Returns current agent presence snapshot.

```json
{
  "agents": [
    {
      "agent_id": "requirements.researcher",
      "display_name": "Researcher",
      "stage": "requirements",
      "state": "thinking",
      "activity": "Analyzing project description",
      "model": "claude-sonnet-4-6",
      "tokens_used": 1240,
      "target_agent": ""
    }
  ]
}
```

### GET /api/v1/projects/{project_id}/conversation

Returns conversation ring buffer.

```json
{
  "entries": [
    {
      "agent_id": "requirements.researcher",
      "display_name": "Researcher",
      "stage": "requirements",
      "message": "Identified 12 user stories from project description",
      "timestamp": "2026-04-05T14:31:12Z",
      "target_agent": ""
    }
  ]
}
```

## WebSocket Event Mapping

How each `EventType` maps to UI updates across Board and Pipeline views:

| Event | Board View Effect | Pipeline View Effect |
|---|---|---|
| `STAGE_STARTED` | Stage group header → "RUNNING" cyan badge, auto-expand group | Stage node glows cyan, connector animates |
| `STAGE_COMPLETED` | Stage group header → "COMPLETED" green badge, auto-collapse after 1s | Stage node turns green, gate node activates |
| `STAGE_FAILED` | Stage group header → "FAILED" red badge, stays expanded | Stage node turns red, pipeline pauses visually |
| `GATE_PASSED` | Gate footer turns green with checkmark + score | Gate node between stages turns green |
| `GATE_FAILED` | Gate footer turns red, shows reasons, expand details | Gate node turns red with tooltip |
| `AGENT_STARTED` | Agent row appears in group (or transitions from Idle) | Agent count badge increments on stage node |
| `AGENT_COMPLETED` | Agent row status pill → Done (green) | Agent count updates (e.g. "2/3 done") |
| `AGENT_ERROR` | Agent row status pill → Error (red flash), row highlighted | Error count badge on stage node |
| `AGENT_THINKING` | Agent row status pill → Thinking (cyan pulse) | -- |
| `AGENT_TOOL_CALL` | Agent row status pill → Tool Use (violet spin), activity column updates | -- |
| `AGENT_REVIEWING` | Agent row status pill → Reviewing (amber pulse) | -- |
| `AGENT_HANDOFF` | Handoff row appears between groups with details | Connector between stage nodes pulses |
| `AGENT_MESSAGE` | New entry in activity feed, agent row activity updates | -- |
| `AGENT_STREAM_CHUNK` | Live text append in agent drawer (if open) | -- |
| `AGENT_STATE_CHANGED` | Agent row status pill + activity column update | -- |
| `APPROVAL_REQUIRED` | Gate footer shows Approve/Reject buttons, nav badge +1 | Gate node pulses magenta with inline actions |
| `FEEDBACK_APPLIED` | Toast notification | -- |
| `PIPELINE_COMPLETED` | All groups show green, metrics bar shows final totals | All nodes green, Gantt bars complete |
| `PIPELINE_FAILED` | Error banner at top, failed group stays expanded + highlighted | Failed node red, pipeline flow stops |

## Model Tiers & Configured Models

The UI displays whichever model string arrives in the WebSocket event `model` field. Models are configured per tier in `.env` and resolved by `llm/gateway.py`:

| Tier | Env Variable | Current Model | Fallback |
|---|---|---|---|
| PLANNING | `COLETTE_DEFAULT_PLANNING_MODEL` | `qwen/qwen3.6-plus:free` | `google/gemma-4-31b-it` |
| EXECUTION | `COLETTE_DEFAULT_EXECUTION_MODEL` | `qwen/qwen3.6-plus:free` | `google/gemma-4-31b-it` |
| VALIDATION | `COLETTE_DEFAULT_VALIDATION_MODEL` | `qwen/qwen3.6-plus:free` | `google/gemma-4-31b-it` |

The UI should:
- Display the raw model string from events (not hardcode model names)
- Show a tier badge alongside the model name (PLANNING / EXECUTION / VALIDATION)
- Color-code tiers: Planning = purple (`--purple`), Execution = blue (`--accent`), Validation = amber (`--amber`)
- When a fallback fires, show the fallback model with a "fallback" badge

### Model Column Display

In the board's Model column, show a compact model string with a tier badge:

```
claude-sonnet-4-6  [EXECUTION]     ← blue badge
claude-opus-4-6    [PLANNING]      ← purple badge
claude-haiku-4-5   [VALIDATION]    ← amber badge
```

If fallback triggered, append a small "fallback" indicator:
```
google/gemma-4-31b-it  [EXECUTION] [↻ fallback]
```

In the agent drawer, show the full model detail card:
```
+-------------------------------------------+
| Model                                     |
| qwen/qwen3.6-plus:free                   |
| Tier: EXECUTION (cyan)                    |
| Fallback chain: google/gemma-4-31b-it     |
| Tokens: 1,240 / 60,000 budget            |
+-------------------------------------------+
```

## Agent Roster by Stage

Agents that appear in each stage room:

| Stage | Agents |
|---|---|
| Requirements | Researcher, Analyst |
| Design | Architect, API Designer, UI Designer |
| Implementation | Backend Dev, Frontend Dev, Database Dev, Verifier, Architect Agent, Refactor Agent, Test Agent |
| Testing | Unit Tester, Integration Tester, Security Scanner |
| Deployment | CI/CD Engineer, Infra Engineer |
| Monitoring | Observability Agent, Incident Response |

## Design Previews

Static HTML mockups generated via Google Stitch, located in `web/stitch-preview/`. Open any file in a browser to view the design.

| Screen | File | Description |
|---|---|---|
| **Agent Board** | [`web/stitch-preview/agent-board.html`](../web/stitch-preview/agent-board.html) | Main view — monday.com-style agent table grouped by pipeline stage |
| **Pipeline View** | [`web/stitch-preview/pipeline-view.html`](../web/stitch-preview/pipeline-view.html) | Orchestration DAG with stage nodes, gate checkpoints, Gantt timeline |
| **Project List** | [`web/stitch-preview/project-list.html`](../web/stitch-preview/project-list.html) | Project cards with status summary and pipeline progress |
| **Project List (alt)** | [`web/stitch-preview/project-list-2.html`](../web/stitch-preview/project-list-2.html) | Alternate project list layout |
| **Dashboard (legacy)** | [`web/stitch-preview/dashboard.html`](../web/stitch-preview/dashboard.html) | Earlier office-floor concept (superseded by Board View) |

These are reference designs only — the actual React implementation will follow the component architecture in this doc.

## Dependencies

- Node.js 20+ (for Vite dev server)
- Existing FastAPI backend running on port 8000
- No new Python dependencies
