import { create } from 'zustand'
import type {
  AgentPresence,
  ApprovalRequest,
  ConversationEntry,
  PipelineEvent,
  StageInfo,
  ToolCall,
} from '../types/events'
import { EventType } from '../types/events'
import { useTerminalStore } from './terminal'
import { useDecisionStore } from './decisions'
import { useArtifactStore } from './artifacts'

const MAX_EVENTS = 200

interface PipelineStore {
  stages: Record<string, StageInfo>
  agents: Record<string, AgentPresence>
  conversation: ConversationEntry[]
  events: PipelineEvent[]
  approvals: ApprovalRequest[]
  agentTools: Record<string, ToolCall[]>
  handleEvent: (event: PipelineEvent) => void
  setInitialState: (agents: AgentPresence[], conversation: ConversationEntry[]) => void
  approveGate: (gateId: string) => Promise<void>
  rejectGate: (gateId: string) => Promise<void>
}

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  stages: {},
  agents: {},
  conversation: [],
  agentTools: {},
  events: [],
  approvals: [],

  handleEvent: (event: PipelineEvent) => {
    const state = get()
    const events = [...state.events, event].slice(-MAX_EVENTS)
    const eventType = event.type ?? (event as unknown as Record<string, unknown>).event_type

    const updates: Partial<PipelineStore> = { events }

    // Helper: upsert an agent entry from any agent-level event
    const upsertAgent = (
      agentId: string,
      agentState: AgentPresence['state'],
      extra?: Partial<AgentPresence>,
    ) => {
      const existing = (updates.agents ?? state.agents)[agentId]
      updates.agents = {
        ...(updates.agents ?? state.agents),
        [agentId]: {
          agent_id: agentId,
          display_name: existing?.display_name ?? agentId,
          stage: event.stage ?? existing?.stage ?? '',
          state: agentState,
          activity: event.message ?? existing?.activity ?? '',
          model: event.model ?? existing?.model ?? '',
          tokens_used: event.tokens_used ?? existing?.tokens_used ?? 0,
          target_agent: existing?.target_agent ?? '',
          started_at: existing?.started_at ?? event.timestamp,
          ...extra,
        },
      }
    }

    if (eventType === EventType.STAGE_STARTED && event.stage) {
      updates.stages = {
        ...state.stages,
        [event.stage]: {
          name: event.stage,
          status: 'running',
          elapsed_ms: 0,
          agent_count: 0,
          active_agents: [],
          gate_result: null,
        },
      }
    }

    if (eventType === EventType.STAGE_COMPLETED && event.stage) {
      const existing = state.stages[event.stage]
      updates.stages = {
        ...state.stages,
        [event.stage]: {
          ...existing,
          name: event.stage,
          status: 'completed',
          elapsed_ms: (event.elapsed_seconds ?? 0) * 1000,
          agent_count: existing?.agent_count ?? 0,
          active_agents: [],
          gate_result: existing?.gate_result ?? null,
        },
      }
    }

    if (eventType === EventType.STAGE_FAILED && event.stage) {
      const existing = state.stages[event.stage]
      updates.stages = {
        ...state.stages,
        [event.stage]: {
          ...existing,
          name: event.stage,
          status: 'failed',
          elapsed_ms: (event.elapsed_seconds ?? 0) * 1000,
          agent_count: existing?.agent_count ?? 0,
          active_agents: [],
          gate_result: existing?.gate_result ?? null,
        },
      }
    }

    // Build agent presence from actual backend events
    if (eventType === EventType.AGENT_THINKING && event.agent) {
      upsertAgent(event.agent, 'thinking')
    }

    if (eventType === EventType.AGENT_TOOL_CALL && event.agent) {
      upsertAgent(event.agent, 'tool_use')
      // Track tool call
      const detail = event.detail ?? {}
      const toolCall: ToolCall = {
        tool_call_id: (detail.tool_call_id as string) ?? `tc-${Date.now()}`,
        tool_name: (detail.tool_name as string) ?? 'unknown',
        status: 'running',
        duration_ms: undefined,
        arguments_preview: (detail.arguments as string) ?? undefined,
        result_preview: undefined,
        timestamp: event.timestamp,
      }
      const existing = state.agentTools[event.agent] ?? []
      updates.agentTools = {
        ...(updates.agentTools ?? state.agentTools),
        [event.agent]: [...existing, toolCall],
      }
    }

    if (eventType === EventType.AGENT_TOOL_RESULT && event.agent) {
      const detail = event.detail ?? {}
      const callId = (detail.tool_call_id as string) ?? ''
      const existing = (updates.agentTools ?? state.agentTools)[event.agent] ?? []
      updates.agentTools = {
        ...(updates.agentTools ?? state.agentTools),
        [event.agent]: existing.map((tc) =>
          tc.tool_call_id === callId
            ? {
                ...tc,
                status: (detail.status as ToolCall['status']) ?? 'success',
                duration_ms: (detail.duration_ms as number) ?? undefined,
                result_preview: (detail.result_preview as string) ?? undefined,
              }
            : tc,
        ),
      }
    }

    if (eventType === EventType.AGENT_REVIEWING && event.agent) {
      upsertAgent(event.agent, 'reviewing')
    }

    if (eventType === EventType.AGENT_HANDOFF && event.agent) {
      const detail = event.detail ?? {}
      upsertAgent(event.agent, 'handing_off', {
        target_agent: (detail.target_agent as string) ?? '',
      })
    }

    if (eventType === EventType.AGENT_STARTED && event.agent) {
      upsertAgent(event.agent, 'thinking')
    }

    if (eventType === EventType.AGENT_COMPLETED && event.agent) {
      upsertAgent(event.agent, 'done')
    }

    if (eventType === EventType.AGENT_ERROR && event.agent) {
      upsertAgent(event.agent, 'error')
    }

    if (eventType === EventType.AGENT_STATE_CHANGED && event.agent) {
      const detail = event.detail ?? {}
      upsertAgent(
        event.agent,
        (detail.state as AgentPresence['state']) ?? 'idle',
        {
          display_name: (detail.display_name as string) || event.agent,
          target_agent: (detail.target_agent as string) ?? '',
          started_at: (detail.started_at as string) ?? event.timestamp,
        },
      )
    }

    if (eventType === EventType.AGENT_STREAM_CHUNK && event.agent) {
      // Keep agent visible during streaming — don't overwrite activity with chunk text
      const existing = (updates.agents ?? state.agents)[event.agent]
      if (existing) {
        upsertAgent(event.agent, 'thinking', { activity: existing.activity })
      }
      // Feed chunk to Live Terminal
      const chunk = event.message ?? (event.detail?.chunk as string) ?? ''
      if (chunk) {
        useTerminalStore.getState().appendChunk(
          event.agent,
          chunk,
          event.stage ?? '',
          existing?.display_name ?? event.agent,
        )
      }
    }

    if (eventType === EventType.AGENT_MESSAGE && event.agent) {
      // Update agent presence with latest activity + token info
      upsertAgent(event.agent, (updates.agents ?? state.agents)[event.agent]?.state ?? 'thinking')
      updates.conversation = [
        ...state.conversation,
        {
          agent_id: event.agent,
          display_name: event.agent,
          stage: event.stage ?? '',
          message: event.message ?? '',
          timestamp: event.timestamp,
          target_agent: '',
        },
      ]
    }

    if (eventType === EventType.GATE_PASSED && event.stage) {
      const detail = event.detail ?? {}
      const existing = state.stages[event.stage]
      if (existing) {
        updates.stages = {
          ...(updates.stages ?? state.stages),
          [event.stage]: {
            ...existing,
            gate_result: {
              name: (detail.gate_name as string) ?? event.stage,
              passed: true,
              score: (detail.score as number) ?? 1,
              reasons: (detail.reasons as string[]) ?? [],
              needs_approval: false,
            },
          },
        }
      }
      // Feed to Decision Rail
      useDecisionStore.getState().addEntry({
        id: `gate-pass-${event.stage}-${event.timestamp}`,
        type: 'gate_passed',
        timestamp: event.timestamp,
        stage: event.stage,
        title: `${event.stage} Gate`,
        detail: 'Auto-approved',
        score: (detail.score as number) ?? 1,
        threshold: (detail.threshold as number) ?? undefined,
        reasons: (detail.reasons as string[]) ?? [],
        resolved: true,
      })
    }

    if (eventType === EventType.GATE_FAILED && event.stage) {
      const detail = event.detail ?? {}
      const existing = state.stages[event.stage]
      if (existing) {
        updates.stages = {
          ...(updates.stages ?? state.stages),
          [event.stage]: {
            ...existing,
            gate_result: {
              name: (detail.gate_name as string) ?? event.stage,
              passed: false,
              score: (detail.score as number) ?? 0,
              reasons: (detail.reasons as string[]) ?? [],
              needs_approval: (detail.needs_approval as boolean) ?? false,
            },
          },
        }
      }
      // Feed to Decision Rail
      useDecisionStore.getState().addEntry({
        id: `gate-fail-${event.stage}-${event.timestamp}`,
        type: 'gate_failed',
        timestamp: event.timestamp,
        stage: event.stage,
        title: `${event.stage} Gate`,
        detail: event.message ?? 'Gate check failed',
        score: (detail.score as number) ?? 0,
        threshold: (detail.threshold as number) ?? undefined,
        reasons: (detail.reasons as string[]) ?? [],
        resolved: true,
      })
    }

    if (eventType === EventType.APPROVAL_REQUIRED) {
      const detail = event.detail ?? {}
      const approvalId = (detail.id as string) ?? ''
      updates.approvals = [
        ...state.approvals,
        {
          id: approvalId,
          gate_name: (detail.gate_name as string) ?? '',
          stage: event.stage ?? '',
          risk_level: (detail.risk_level as string) ?? 'medium',
          reason: event.message ?? '',
          score: (detail.score as number) ?? 0,
          threshold: (detail.threshold as number) ?? 0,
          requested_at: event.timestamp,
        },
      ]
      // Feed to Decision Rail
      useDecisionStore.getState().addEntry({
        id: `approval-${approvalId}-${event.timestamp}`,
        type: 'approval_required',
        timestamp: event.timestamp,
        stage: event.stage ?? '',
        title: `${event.stage ?? ''} Gate`,
        detail: event.message ?? 'Approval required',
        score: (detail.score as number) ?? 0,
        threshold: (detail.threshold as number) ?? 0,
        approvalId,
        resolved: false,
      })
    }

    // Handle artifact generation
    if (eventType === EventType.ARTIFACT_GENERATED) {
      const detail = event.detail ?? {}
      useArtifactStore.getState().addFile({
        id: `artifact-${event.timestamp}-${(detail.path as string) ?? ''}`,
        path: (detail.path as string) ?? 'unknown',
        stage: event.stage ?? '',
        agent: event.agent ?? '',
        language: (detail.language as string) ?? '',
        size_bytes: (detail.size_bytes as number) ?? 0,
        content_preview: (detail.content_preview as string) ?? undefined,
        isNew: true,
        timestamp: event.timestamp,
      })
    }

    set(updates)
  },

  setInitialState: (agents, conversation) => {
    const agentsMap: Record<string, AgentPresence> = {}
    for (const a of agents) {
      agentsMap[a.agent_id] = a
    }
    set({ agents: agentsMap, conversation })
  },

  approveGate: async (gateId: string) => {
    await fetch(`/api/v1/approvals/${gateId}/approve`, { method: 'POST' })
    set((s) => ({
      approvals: s.approvals.filter((a) => a.id !== gateId),
    }))
  },

  rejectGate: async (gateId: string) => {
    await fetch(`/api/v1/approvals/${gateId}/reject`, { method: 'POST' })
    set((s) => ({
      approvals: s.approvals.filter((a) => a.id !== gateId),
    }))
  },
}))
