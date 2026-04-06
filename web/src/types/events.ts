export type AgentState =
  | 'idle'
  | 'thinking'
  | 'tool_use'
  | 'reviewing'
  | 'handing_off'
  | 'done'
  | 'error'

export type StageStatus = 'pending' | 'running' | 'completed' | 'failed'

export type ModelTier = 'PLANNING' | 'EXECUTION' | 'VALIDATION' | 'REASONING'

export interface AgentPresence {
  agent_id: string
  display_name: string
  stage: string
  state: AgentState
  activity: string
  model: string
  tokens_used: number
  target_agent: string
  started_at: string
}

export interface ConversationEntry {
  agent_id: string
  display_name: string
  stage: string
  message: string
  timestamp: string
  target_agent: string
}

export const EventType = {
  STAGE_STARTED: 'stage_started',
  STAGE_COMPLETED: 'stage_completed',
  STAGE_FAILED: 'stage_failed',
  GATE_PASSED: 'gate_passed',
  GATE_FAILED: 'gate_failed',
  AGENT_STARTED: 'agent_started',
  AGENT_COMPLETED: 'agent_completed',
  AGENT_ERROR: 'agent_error',
  AGENT_THINKING: 'agent_thinking',
  AGENT_TOOL_CALL: 'agent_tool_call',
  AGENT_REVIEWING: 'agent_reviewing',
  AGENT_HANDOFF: 'agent_handoff',
  AGENT_MESSAGE: 'agent_message',
  AGENT_STREAM_CHUNK: 'agent_stream_chunk',
  AGENT_STATE_CHANGED: 'agent_state_changed',
  APPROVAL_REQUIRED: 'approval_required',
  FEEDBACK_APPLIED: 'feedback_applied',
  PIPELINE_COMPLETED: 'pipeline_completed',
  PIPELINE_FAILED: 'pipeline_failed',
  PIPELINE_PAUSED: 'pipeline_paused',
  PIPELINE_RESUMED: 'pipeline_resumed',
  STAGE_RESTARTED: 'stage_restarted',
  STAGE_SKIPPED: 'stage_skipped',
  OPERATOR_FEEDBACK: 'operator_feedback',
  OPERATOR_MESSAGE: 'operator_message',
  HANDOFF_EDITED: 'handoff_edited',
  ARTIFACT_GENERATED: 'artifact_generated',
  AGENT_TOOL_RESULT: 'agent_tool_result',
} as const

export type EventType = (typeof EventType)[keyof typeof EventType]

export interface PipelineEvent {
  type: EventType
  data: Record<string, unknown>
  timestamp: string
  project_id?: string
  stage?: string
  agent?: string
  model?: string
  message?: string
  detail?: Record<string, unknown>
  elapsed_seconds?: number
  tokens_used?: number
}

export interface ApprovalRequest {
  id: string
  gate_name: string
  stage: string
  risk_level: string
  reason: string
  score: number
  threshold: number
  requested_at: string
}

export interface GateResult {
  name: string
  passed: boolean
  score: number
  reasons: string[]
  needs_approval: boolean
}

export interface ToolCall {
  tool_call_id: string
  tool_name: string
  status: 'running' | 'success' | 'error' | 'retried'
  duration_ms?: number
  arguments_preview?: string
  result_preview?: string
  timestamp: string
}

export interface StageInfo {
  name: string
  status: StageStatus
  elapsed_ms: number
  agent_count: number
  active_agents: string[]
  gate_result: GateResult | null
}
