import type { AgentState, ModelTier, StageStatus } from '../types/events'

export function statusColor(state: AgentState): string {
  const map: Record<AgentState, string> = {
    idle: 'var(--text-secondary)',
    thinking: 'var(--accent)',
    tool_use: 'var(--purple)',
    reviewing: 'var(--amber)',
    handing_off: 'var(--accent)',
    done: 'var(--green)',
    error: 'var(--red)',
  }
  return map[state]
}

export function tierColor(tier: ModelTier): string {
  const map: Record<ModelTier, string> = {
    PLANNING: 'var(--purple)',
    EXECUTION: 'var(--accent)',
    VALIDATION: 'var(--amber)',
    REASONING: 'var(--purple)',
  }
  return map[tier]
}

export function stageStatusColor(status: StageStatus): string {
  const map: Record<StageStatus, string> = {
    pending: 'var(--text-secondary)',
    running: 'var(--accent)',
    completed: 'var(--green)',
    failed: 'var(--red)',
  }
  return map[status]
}
