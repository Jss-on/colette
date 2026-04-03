---
id: "phase-7a-middleware-2026-04-04"
status: "backlog"
priority: "critical"
assignee: "claude"
dueDate: "2026-04-04"
created: "2026-04-04T00:00:00Z"
modified: "2026-04-04T00:00:00Z"
completedAt: null
labels: ["phase", "phase-7a"]
order: "a6"
---
# Phase 7a: Middleware Architecture

## Goal
Composable middleware stacks for agents, replacing monolithic supervisors.

## Tasks
- [ ] Create agents/middleware/protocol.py
- [ ] Create agents/middleware/event_emission.py
- [ ] Create agents/middleware/token_budget.py
- [ ] Create agents/middleware/todo_list.py
- [ ] Refactor design/supervisor.py as proof-of-concept
- [ ] Create agents/middleware/__init__.py
- [ ] Write tests
- [ ] make check passes
- [ ] git commit and push

## Notes
No dependencies - can run in parallel with Phase 1.
