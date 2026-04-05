import { create } from 'zustand'
import type {
  AgentPresence,
  ApprovalRequest,
  ConversationEntry,
  PipelineEvent,
  StageInfo,
} from '../types/events'
import { EventType } from '../types/events'

const MAX_EVENTS = 200

interface PipelineStore {
  stages: Record<string, StageInfo>
  agents: Record<string, AgentPresence>
  conversation: ConversationEntry[]
  events: PipelineEvent[]
  approvals: ApprovalRequest[]
  handleEvent: (event: PipelineEvent) => void
  setInitialState: (agents: AgentPresence[], conversation: ConversationEntry[]) => void
  approveGate: (gateId: string) => Promise<void>
  rejectGate: (gateId: string) => Promise<void>
}

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  stages: {},
  agents: {},
  conversation: [],
  events: [],
  approvals: [],

  handleEvent: (event: PipelineEvent) => {
    const state = get()
    const events = [...state.events, event].slice(-MAX_EVENTS)
    const eventType = event.type ?? (event as unknown as Record<string, unknown>).event_type

    const updates: Partial<PipelineStore> = { events }

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

    if (eventType === EventType.AGENT_STATE_CHANGED && event.agent) {
      const detail = event.detail ?? {}
      updates.agents = {
        ...state.agents,
        [event.agent]: {
          agent_id: event.agent,
          display_name: (detail.display_name as string) || event.agent,
          stage: event.stage ?? '',
          state: (detail.state as AgentPresence['state']) ?? 'idle',
          activity: event.message ?? '',
          model: event.model ?? '',
          tokens_used: event.tokens_used ?? 0,
          target_agent: (detail.target_agent as string) ?? '',
          started_at: (detail.started_at as string) ?? event.timestamp,
        },
      }
    }

    if (eventType === EventType.AGENT_MESSAGE && event.agent) {
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
    }

    if (eventType === EventType.APPROVAL_REQUIRED) {
      const detail = event.detail ?? {}
      updates.approvals = [
        ...state.approvals,
        {
          id: (detail.id as string) ?? '',
          gate_name: (detail.gate_name as string) ?? '',
          stage: event.stage ?? '',
          risk_level: (detail.risk_level as string) ?? 'medium',
          reason: event.message ?? '',
          score: (detail.score as number) ?? 0,
          threshold: (detail.threshold as number) ?? 0,
          requested_at: event.timestamp,
        },
      ]
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
