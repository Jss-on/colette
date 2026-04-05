# Colette Mission Control -- Vision & Design System

> Reference document for the Colette web UI redesign. Covers the design philosophy, visual language, component taxonomy, and interaction patterns.

## 1. Design Philosophy

Colette is **not** a monitoring dashboard. It is a **command center** for directing a fleet of AI agents that build software autonomously. The UI must make the user feel **in control** -- not like they are watching a loading bar.

### Core Principles

| Principle | What It Means |
|-----------|---------------|
| **Alive, not static** | Every active element breathes, pulses, or streams. Idle screens show ambient motion, not dead gray. |
| **Outputs front-and-center** | The LLM thinking and writing is the most interesting thing happening. It must never be hidden behind 2+ clicks. |
| **Progressive disclosure** | Show the right density at each zoom level: project list -> war room -> agent detail -> raw output. |
| **Decision support** | When a gate needs approval, the UI must push context to the user, not wait for them to discover it. |
| **Persistent history** | Every run, every gate decision, every artifact must be retrievable after the fact -- not lost on page refresh. |

### Mental Model: The Office Floor

Imagine a tech company building your software. Six rooms (stages), each with a team of specialists. You stand in a glass-walled observation deck above the floor. You can see:
- Which rooms are lit up (active stages)
- Who is at their desk (agent presence)
- What they are typing (live stream)
- What they have produced (artifacts)
- Where the hand-off checkpoints are (gates)
- When someone raises their hand for your approval

The UI spatializes this metaphor.

---

## 2. Design Tokens

### 2.1 Color System

Based on the Stitch previews with Material Design 3 extended palette.

#### Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--primary` | `#4cd7f6` | Active elements, running state, interactive links, pipeline progress |
| `--primary-container` | `#06b6d4` | Filled buttons, active tab indicators, strong accents |
| `--on-primary` | `#003640` | Text on primary containers |
| `--secondary` | `#fbabff` | Agent identity accents, approval states, secondary actions |
| `--secondary-container` | `#ae05c6` | Agent badges, secondary highlights |
| `--tertiary` | `#4edea3` | Success state, completed stages, passed gates |
| `--tertiary-container` | `#1bbd85` | Completed stage backgrounds, success badges |
| `--error` | `#ffb4ab` | Failed state, critical alerts, rejected gates |
| `--error-container` | `#93000a` | Error backgrounds |
| `--surface` | `#0f131f` | Page background |
| `--surface-dim` | `#0a0e1a` | Deepest background (code blocks, terminal) |
| `--surface-container-lowest` | `#0a0e1a` | Sidebar background |
| `--surface-container-low` | `#171b28` | Card background (resting) |
| `--surface-container` | `#1b1f2c` | Card background (elevated) |
| `--surface-container-high` | `#262a37` | Active card, hover state |
| `--surface-container-highest` | `#313442` | Chips, badges, inline elements |
| `--on-surface` | `#dfe2f3` | Primary text |
| `--on-surface-variant` | `#bcc9cd` | Secondary / muted text |
| `--outline` | `#869397` | Subtle borders, disabled text |
| `--outline-variant` | `#3d494c` | Structural borders, dividers |

#### State Colors (Agent States)

| State | Color | Animation |
|-------|-------|-----------|
| `thinking` | `--primary` (#4cd7f6) | Slow pulse glow (2s cycle) |
| `tool_use` | `--tertiary` (#d5bbff) purple | Gear icon + tool name badge |
| `reviewing` | `--secondary` (#fbabff) | Subtle shimmer |
| `handing_off` | `--primary` | Data-packet animation toward target |
| `done` | `--tertiary` (#4edea3) | Solid, no animation |
| `error` | `--error` (#f85149) | Flash once, then solid |
| `idle` | `--outline` (#7d8590) | Dim, 60% opacity |

### 2.2 Typography

| Role | Font | Weight | Usage |
|------|------|--------|-------|
| `font-headline` | Space Grotesk | 700 | Page titles, stage names, agent names |
| `font-body` | Manrope / Inter | 400-500 | Body text, descriptions, messages |
| `font-label` | Inter | 500-600 | Labels, badges, small UI text |
| `font-mono` | JetBrains Mono | 400-500 | Data values, code, timestamps, terminal |

#### Scale

| Level | Size | Line Height | Usage |
|-------|------|-------------|-------|
| Display | 32px | 1.2 | Project name on dashboard |
| H1 | 24px | 1.3 | Page headings ("Active Projects") |
| H2 | 18px | 1.35 | Section headings (stage names) |
| H3 | 14px | 1.4 | Card titles, agent names |
| Body | 14px | 1.5 | Descriptions, messages |
| Label | 12px | 1.4 | Badges, metadata |
| Caption | 10px | 1.3 | Timestamps, mono data, KPI labels |
| Micro | 9px | 1.2 | Status bar indicators |

### 2.3 Spacing & Layout

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | 4px | Inline gaps, badge padding |
| `--space-sm` | 8px | Between related items |
| `--space-md` | 16px | Card padding, section gaps |
| `--space-lg` | 24px | Between sections |
| `--space-xl` | 32px | Page margins |
| `--space-2xl` | 48px | Major section separation |

### 2.4 Elevation & Effects

```css
/* Glass card (primary surface treatment) */
.glass-card {
  background: rgba(17, 24, 39, 0.7);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(30, 41, 59, 0.5);
}
.glass-card:hover {
  background: rgba(26, 35, 50, 0.9);
  border-color: rgba(76, 215, 246, 0.3);
}

/* Glow effect for active elements */
.glow-cyan {
  box-shadow: 0 0 20px rgba(76, 215, 246, 0.15);
}

/* Pulse animation for running state */
@keyframes pulse-cyan {
  0%   { box-shadow: 0 0 0 0 rgba(76, 215, 246, 0.4); }
  70%  { box-shadow: 0 0 0 10px rgba(76, 215, 246, 0); }
  100% { box-shadow: 0 0 0 0 rgba(76, 215, 246, 0); }
}
```

### 2.5 Border Radius

Tight, technical aesthetic (not bubbly):

| Token | Value | Usage |
|-------|-------|-------|
| `rounded-DEFAULT` | 2px | Micro elements (badges, inline chips) |
| `rounded-lg` | 4px | Buttons, inputs |
| `rounded-xl` | 8px | Cards, panels |
| `rounded-full` | 12px | Avatars, status dots |

### 2.6 Iconography

Material Symbols Outlined (variable weight, variable fill).

Default settings: `'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24`

Key icons by context:

| Context | Icon | Fill Variant |
|---------|------|-------------|
| Requirements stage | `search` | 0 |
| Design stage | `architecture` | 0 |
| Implementation stage | `code` | 0 |
| Testing stage | `bug_report` | 0 |
| Deployment stage | `rocket_launch` | 1 |
| Monitoring stage | `monitoring` | 0 |
| Gate passed | `verified_user` | 1 |
| Gate failed | `warning` | 0 |
| Approval needed | `approval` | 0 |
| Agent thinking | `psychology` | 1 |
| Agent tool use | `build` / `settings` | 0 |
| Agent done | `check_circle` | 1 |
| Agent error | `error` | 1 |
| Handoff | `double_arrow` | 0 |
| Streaming | `stream` | 0 |
| Artifacts | `inventory_2` | 0 |

---

## 3. Page Architecture

### 3.1 Global Shell

Every page shares:

```
+----------------------------------------------------------+
| HEADER BAR (sticky)                                      |
|  Logo  |  Nav: Missions / Assets / Fleet / Intelligence  |
|        |                          [Notifications] [User] |
+----------------------------------------------------------+
| SIDEBAR (collapsible, lg+ only)                          |
|  Dashboard                                               |
|  Active Ops  <-- current                                 |
|  Archive                                                 |
|  Analytics                                               |
|  System Logs                                             |
|  --------                                                |
|  Deploy New Node                                         |
|  Support | Sign Out                                      |
+----------------------------------------------------------+
| MAIN CONTENT AREA                                        |
|                                                          |
+----------------------------------------------------------+
| STATUS FOOTER (fixed bottom)                             |
|  Status: Nominal | TOTAL_NODES: 04 | RUNNING: 02 | ...  |
+----------------------------------------------------------+
```

### 3.2 Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Project List | Grid of all projects with status, progress bars, agent counts |
| `/projects/:id` | Project Dashboard | The main war room with multiple views |
| `/projects/:id/history` | Run History | All pipeline runs for this project (NEW) |
| `/projects/:id/runs/:runId` | Run Replay | Historical run detail with timeline replay (NEW) |
| `/analytics` | Analytics | Cross-project cost, token, and performance dashboards (NEW) |

### 3.3 Project Dashboard Views

The project dashboard uses a **view switcher** (tabs) for its primary content area plus a **persistent right sidebar**:

```
+---------------------------------------------------+------------------+
| VIEW SWITCHER: [War Room] [Board] [Pipeline] [Artifacts]  |            |
+---------------------------------------------------+  DECISION RAIL   |
|                                                   |                  |
|  PRIMARY VIEW AREA                                |  Gate decisions   |
|  (switches based on active tab)                   |  Approvals        |
|                                                   |  Escalations      |
|                                                   |  Notifications    |
|                                                   |                  |
+---------------------------------------------------+------------------+
| LIVE TERMINAL (resizable, collapsible, ~30% height)                  |
|  [Agent A tab] [Agent B tab] [Agent C tab]                           |
|  > Implementing user authentication service...                       |
|  > Generating JWT token middleware...                                 |
+----------------------------------------------------------------------+
```

---

## 4. Component Taxonomy

### 4.1 War Room View (NEW -- primary view)

**Purpose**: Spatial overview of the entire pipeline. Replaces the flat board as the default landing view.

**Layout**: 3x2 grid of **Stage Room Cards**.

```
+------------------+------------------+------------------+
|   REQUIREMENTS   |     DESIGN       |  IMPLEMENTATION  |
|   [completed]    |   [completed]    |    [running]     |
|  @Researcher [v] |  @Architect [v]  | @Backend [pulse] |
|  @Analyst    [v] |  @API Desn  [v]  | @Frontend [gear] |
|                  |  @UI Design [v]  | @DB Dev   [dim]  |
|            [gate: pass]       [gate: pass]             |
+------------------+------------------+------------------+
|     TESTING      |    DEPLOYMENT    |   MONITORING     |
|    [pending]     |    [pending]     |    [pending]     |
|  @Unit Tstr [dim]| @CI/CD Eng [dim] | @Observ.   [dim] |
|  @Intg Tstr [dim]| @Infra Eng [dim] | @Incident  [dim] |
|  @Sec Scan  [dim]|                  |                  |
+------------------+------------------+------------------+
```

Each **Stage Room Card** contains:
- Stage name header with status badge
- Gate indicator (right edge or bottom edge) showing pass/fail/pending
- Agent chips inside the room: avatar + name + state indicator
- Active agents glow and pulse; idle agents are dimmed
- Clicking a room expands it to a **focused stage view**

**Connections between rooms**:
- Completed gate -> next room: solid glowing connector line
- Pending gate: dashed connector
- Failed gate: red connector with warning icon

### 4.2 Board View (existing, enhanced)

Keep the current table-based view but enhance:

**New columns**:
- **Tools** column: shows last tool called + count (e.g., `filesystem.write (3)`)
- **Output** column: truncated last output line, click to expand

**Enhanced rows**:
- Clicking a row opens agent detail **in the Live Terminal** (bottom panel), not a side drawer
- Handoff rows between stages show what data was passed (e.g., "12 user stories, 5 NFRs")
- Gate footer rows show score, threshold, pass/fail reasons

### 4.3 Pipeline View (existing, enhanced)

**Flow diagram**: Keep the stage-to-gate-to-stage DAG layout.

**Enhancements**:
- Animated data flow: when a stage completes, a particle animation flows through the gate connector to the next stage
- Gate nodes show inline score (e.g., "92%") and click to expand full evaluation
- Gantt timeline below shows real elapsed time per stage with proportional bars
- Summary KPI cards: Total Tokens, Elapsed Time, Active Agents, Errors, Cost Estimate

### 4.4 Artifact Workshop (replaces current Artifacts view)

**Three-panel layout**:

```
+------------------+-------------------------------+------------------+
| FILE TREE        | CODE PREVIEW                  | FILE METADATA    |
| (by stage)       |                               |                  |
|                  | [Tab: main.py] [Tab: api.yml] | Author: @Backend |
| v Requirements   |                               | Stage: impl      |
|   reqs.json      | ```python                     | Size: 2.4 KB     |
| v Design         | from fastapi import FastAPI   | Created: 14:23   |
|   api.yaml       |                               |                  |
|   schema.sql     | app = FastAPI()               | [Download]       |
| v Implementation | ...                           | [View Diff]      |
|   > main.py      | ```                           |                  |
|   models.py      |                               |                  |
+------------------+-------------------------------+------------------+
```

**Key features**:
- **Live file creation**: Files appear in the tree as `ARTIFACT_GENERATED` events arrive, with a pulsing "new" indicator
- **Syntax highlighting**: Use Shiki with the same dark theme
- **Streaming preview**: When an agent is actively writing a file, the code preview shows content appearing token-by-token
- **Diff view**: Toggle between full content and diff-from-previous-stage
- **Download controls**: Individual file, stage ZIP, full project ZIP, export to GitHub

### 4.5 Live Terminal (NEW -- persistent bottom panel)

**Purpose**: Always-visible streaming output from agents. The most important addition.

**Behavior**:
- Pinned to the bottom of the dashboard, height resizable (drag handle), collapsible
- Default height: ~30% of viewport
- Shows **tabs** -- one per agent that has produced output
- Active tab auto-selected to whichever agent is currently streaming
- Tab badges show unread content count when not focused
- Content is the raw `AGENT_STREAM_CHUNK` stream with syntax highlighting where applicable
- Terminal background: `--surface-dim` (#0a0e1a)
- Auto-scrolls to bottom unless user scrolls up (then shows "Jump to latest" button)
- **Split mode**: Hold Ctrl+click a second tab to show two agents side-by-side

### 4.6 Decision Rail (NEW -- persistent right sidebar)

**Purpose**: Chronological log of every decision point, always visible. Replaces the hidden approval queue.

**Width**: 320px, collapsible.

**Entry types**:

1. **Gate Result** (auto-approved):
   ```
   14:22:01  REQUIREMENTS GATE
             Score: 92% (threshold: 85%)
             PASSED -- Auto-approved
             [View Details]
   ```

2. **Approval Required** (needs action):
   ```
   14:23:45  DESIGN GATE  [pulsing amber]
             Score: 78% (threshold: 85%)
             NEEDS APPROVAL
             Missing: API pagination strategy
             [Approve] [Reject] [View Details]
   ```

3. **Agent Escalation**:
   ```
   14:25:12  @Architect flagged:
             "DB schema has circular dependency"
             [Acknowledge] [Override]
   ```

4. **Handoff Marker**:
   ```
   14:26:00  Requirements -> Design
             12 user stories, 5 NFRs, 3 constraints
   ```

**Notifications**: When an approval is needed, the rail entry pulses amber and a browser notification fires (if permitted).

### 4.7 Tool Execution Timeline (NEW)

**Context**: Shown inside the expanded agent detail (either in the Live Terminal or a focused stage view).

**Layout**: Horizontal timeline strip.

```
[filesystem.read 0.3s] --- [git.status 0.1s] --- [terminal.exec 2.1s] --- [filesystem.write 0.4s]
     success                  success               FAILED (1 retry)         success
```

Each block:
- Color: green (success), red (error), amber (retried)
- Hover tooltip: tool arguments (input) and truncated result (output)
- Click to expand: full input/output in a modal or inline panel
- Running tool: animated progress bar within the block

### 4.8 Metrics Bar (enhanced)

**Position**: Fixed below header, always visible.

```
[Pipeline Progress ====45%====] | Tokens: 42,847 | Elapsed: 3m 12s | Errors: 0 | Cost: ~$0.34 | [IMPLEMENTATION badge]
```

**Enhancements over current**:
- **Cost estimate**: calculated from tokens * model pricing
- **Stage badge**: shows current active stage name with pulsing dot
- **Error count**: clickable, opens filtered activity log showing only errors
- **Progress bar**: segmented by stage (6 segments, filled proportionally)

### 4.9 Operator Intervention System (NEW -- always available)

**Purpose**: The operator (you) can intervene at **any point** during pipeline execution -- not just at gate checkpoints. You are always in control. The pipeline works for you, not the other way around.

#### Intervention Levels

| Level | What It Does | When to Use |
|-------|-------------|-------------|
| **Pause Stage** | Freezes the current stage; agents stop after finishing their current LLM call | "Wait, I want to review what the design stage is producing before it finishes" |
| **Pause Pipeline** | Freezes the entire pipeline at the current point | "Hold everything, I need to think about this" |
| **Cancel Pipeline** | Hard-stop; marks run as cancelled, kills in-flight tasks | "This is going in the wrong direction, abort" |
| **Inject Feedback** | Send a message to the active stage's supervisor agent mid-execution | "Use PostgreSQL instead of MongoDB for the database" |
| **Redirect Agent** | Send a targeted instruction to a specific agent while it's working | "@Backend Dev -- use JWT tokens, not session cookies" |
| **Restart Stage** | Re-run the current stage from scratch (discards current stage output, keeps prior stages) | "The design output is wrong, redo it" |
| **Skip Stage** | Mark a stage as complete with manual/external output, advance to next | "I already have the requirements doc, skip to design" |
| **Edit Handoff** | Modify the handoff data between stages before the next stage reads it | "Add an extra user story before design begins" |

#### Command Bar

The primary intervention interface. A command palette (like VS Code's Ctrl+K) that appears as a floating input bar over the dashboard.

**Trigger**: `Ctrl+K` (or `Cmd+K` on Mac), or click the command icon in the header.

```
+------------------------------------------------------------------+
| > Type a command or message to agents...                    [Esc] |
+------------------------------------------------------------------+
  Suggestions:
  /pause          Pause the current stage
  /pause-all      Pause the entire pipeline
  /cancel         Cancel the pipeline
  /restart        Restart the current stage
  /skip           Skip the current stage
  /feedback       Send feedback to the active stage
  /edit-handoff   Edit the last handoff before next stage reads it
  @Backend Dev    Send a direct message to an agent
```

**Behaviors**:
- **Plain text** (no `/` prefix): Treated as feedback -- injected into the current stage's supervisor context as a human message. The supervisor incorporates it into its next decision.
- **`/pause`**: Emits a `PIPELINE_PAUSED` event; agents complete their current LLM call then stop. Stage status becomes `paused`. A "Resume" button appears in the War Room and Metrics Bar.
- **`/pause-all`**: Same but pipeline-level. All stages freeze.
- **`/cancel`**: Calls `POST /projects/{id}/cancel`. Confirmation dialog first.
- **`/restart`**: Calls `POST /projects/{id}/stages/{stage}/restart`. Confirmation dialog: "This will discard current stage output. Prior stages are preserved."
- **`/skip`**: Opens a modal where you can paste or describe the output for the skipped stage. Constructs a synthetic handoff.
- **`/feedback "use PostgreSQL"`**: Injects the message into the pipeline state as `user_feedback` field. The supervisor reads this on its next iteration.
- **`/edit-handoff`**: Opens the last handoff as editable JSON/form in a modal. You can add user stories, change constraints, modify the tech stack, etc. On save, the pipeline state is updated before the next stage reads it.
- **`@AgentName message`**: Sends a targeted message to a specific agent. Displayed in the agent's conversation and factored into its next LLM call.

#### Persistent Controls

Always visible in the Metrics Bar (no need to open Command Bar for common actions):

```
[Pipeline Progress ====45%====] | ... | [IMPLEMENTATION] | [Pause] [Cancel] | [Command: Ctrl+K]
```

- **Pause button**: Toggles between Pause/Resume. Shows a `pause_circle` / `play_circle` icon.
- **Cancel button**: Always visible with `cancel` icon. Requires confirmation.

#### Stage-Level Controls

Each stage room in the War Room (and each stage header in the Board view) has a context menu (right-click or `...` button):

```
+-------------------------+
| Pause Stage             |
| Restart Stage           |
| Skip Stage              |
| Send Feedback           |
| View Handoff Input      |
| Edit Handoff Output     |
+-------------------------+
```

#### Agent-Level Controls

Each agent chip/row has a context menu:

```
+-------------------------+
| Send Message            |
| View Output             |
| View Tool Calls         |
| Restart Agent           |  (re-invoke this specific agent)
+-------------------------+
```

#### Decision Rail Integration

Interventions appear in the Decision Rail as entries:

```
14:24:30  OPERATOR INTERVENTION
          [Paused] Implementation stage
          Reason: "Reviewing design output"
          [Resume]

14:25:15  OPERATOR FEEDBACK
          "Use PostgreSQL instead of MongoDB"
          Injected into: Implementation supervisor
          [View Context]

14:26:00  OPERATOR REDIRECT
          @Backend Dev: "Use JWT tokens"
          Status: Delivered, agent acknowledged
```

#### Keyboard Shortcuts for Intervention

| Key | Action |
|-----|--------|
| `Ctrl+K` / `Cmd+K` | Open Command Bar |
| `Space` | Pause/Resume pipeline (when not in an input field) |
| `Ctrl+.` | Quick feedback -- opens inline input at the bottom of the active stage room |

#### Backend Requirements

New endpoints and events needed (added to `02-backend-api-requirements.md`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /projects/{id}/pause` | POST | Pause pipeline (set flag, agents stop after current call) |
| `POST /projects/{id}/resume` | POST | Resume paused pipeline (already exists for approvals, extend) |
| `POST /projects/{id}/stages/{stage}/restart` | POST | Re-run a stage from scratch |
| `POST /projects/{id}/stages/{stage}/skip` | POST | Skip stage with synthetic handoff |
| `POST /projects/{id}/feedback` | POST | Inject feedback message into pipeline state |
| `POST /projects/{id}/agents/{agent_id}/message` | POST | Send targeted message to agent |

New event types:

| Event | Description |
|-------|-------------|
| `PIPELINE_PAUSED` | Pipeline was paused by operator |
| `PIPELINE_RESUMED` | Pipeline was resumed by operator |
| `STAGE_RESTARTED` | Stage was restarted by operator |
| `STAGE_SKIPPED` | Stage was skipped by operator |
| `OPERATOR_FEEDBACK` | Operator injected feedback |
| `OPERATOR_MESSAGE` | Operator sent message to specific agent |

New pipeline state fields:

```python
# In PipelineState TypedDict:
user_feedback: list[str]        # Operator feedback messages (reducer: operator.add)
paused: bool                     # Whether pipeline is currently paused
paused_at: str | None            # ISO timestamp of pause
paused_by: str | None            # Who paused it
```

---

## 5. Interaction Patterns

### 5.1 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `W` | Switch to War Room view |
| `B` | Switch to Board view |
| `P` | Switch to Pipeline view |
| `A` | Switch to Artifacts view |
| `D` | Toggle Decision Rail |
| `T` | Toggle Live Terminal |
| `` ` `` (backtick) | Focus Live Terminal |
| `Ctrl+K` / `Cmd+K` | Open Command Bar |
| `Space` | Pause/Resume pipeline (when not in input) |
| `Ctrl+.` | Quick inline feedback |
| `Esc` | Close expanded panels / deselect / dismiss Command Bar |
| `1-6` | Jump to stage 1-6 in War Room |
| `?` | Show keyboard shortcuts help |

### 5.2 Navigation Flow

```
Project List
  |
  +-- click project card -->  Project Dashboard (War Room default)
                                |
                                +-- click stage room --> Focused Stage View
                                |     |
                                |     +-- click agent --> Agent detail in Live Terminal
                                |
                                +-- switch tab --> Board / Pipeline / Artifacts
                                |
                                +-- click "History" in sidebar --> Run History
                                      |
                                      +-- click run --> Run Replay (timeline scrubber)
```

### 5.3 Responsive Breakpoints

| Breakpoint | Layout Changes |
|------------|----------------|
| `>= 1440px` (xl) | Full layout: sidebar + main + decision rail + terminal |
| `>= 1024px` (lg) | Collapse sidebar to icons. Decision rail overlays. |
| `>= 768px` (md) | Stack terminal below main. Decision rail becomes a sheet. |
| `< 768px` (sm) | Single column. Bottom nav bar. Terminal is a full-screen sheet. |

### 5.4 Mobile Bottom Navigation

```
[Live Stream] [Artifacts] [Approvals] [Timeline]
```

(Matches the Stitch dashboard.html mobile nav design.)

---

## 6. Animation Catalog

| Animation | Duration | Easing | Used For |
|-----------|----------|--------|----------|
| `pulse-cyan` | 2s infinite | ease-in-out | Running state indicator |
| `fade-in` | 200ms | ease-out | New elements appearing |
| `slide-in-right` | 300ms | cubic-bezier(0.16, 1, 0.3, 1) | Decision rail expand |
| `slide-up` | 300ms | cubic-bezier(0.16, 1, 0.3, 1) | Terminal expand |
| `data-packet` | 800ms | ease-in-out | Handoff between agents |
| `gate-pass` | 500ms | ease-out | Gate checkpoint animation |
| `typing-dots` | 1.4s infinite | steps | Agent thinking indicator |
| `stream-cursor` | 1s infinite | steps(2) | Blinking cursor in terminal |
| `room-expand` | 400ms | cubic-bezier(0.16, 1, 0.3, 1) | Stage room -> focused view |

---

## 7. Accessibility

- All interactive elements must be keyboard navigable
- Color is never the only indicator of state (icons + text labels always accompany color)
- Minimum contrast ratio: 4.5:1 for text, 3:1 for large text and UI components
- Animations respect `prefers-reduced-motion`: disable pulse/glow, keep layout transitions
- Screen reader announcements for gate pass/fail and approval requests
- Focus ring: 2px `--primary` outline with 2px offset

---

## 8. Relationship to Stitch Previews

The HTML files in `web/stitch-preview/` are static design explorations:

| File | What It Covers | Status in This Spec |
|------|---------------|---------------------|
| `project-list.html` / `project-list-2.html` | Project grid with glass cards | Adopted as Project List page design |
| `dashboard.html` | War Room (office floor) + conversation sidebar | Adopted as War Room view + Decision Rail concept |
| `pipeline-view.html` | Project grid (misnamed; shows project list variant) | Design tokens adopted; layout superseded |
| `agent-board.html` | Table-based board with expanded/collapsed stages | Adopted as Board view with enhancements |

These previews establish the visual language. The implementation must bring them to life with real data, WebSocket events, and the new components (Live Terminal, Tool Timeline, Artifact Workshop) that the previews do not cover.
