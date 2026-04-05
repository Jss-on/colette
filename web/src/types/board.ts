import type { AgentPresence, GateResult, StageInfo } from './events'

export interface BoardColumn {
  key: string
  label: string
  width: string
  align: 'left' | 'center' | 'right'
}

export const BOARD_COLUMNS: BoardColumn[] = [
  { key: 'agent', label: 'Agent', width: '200px', align: 'left' },
  { key: 'status', label: 'Status', width: '120px', align: 'center' },
  { key: 'activity', label: 'Activity', width: '1fr', align: 'left' },
  { key: 'model', label: 'Model', width: '160px', align: 'left' },
  { key: 'tokens', label: 'Tokens', width: '100px', align: 'right' },
  { key: 'duration', label: 'Duration', width: '100px', align: 'right' },
]

export interface HandoffData {
  from_stage: string
  to_stage: string
  stories_count: number
  nfrs_count: number
  score: number
}

export interface StageGroup {
  stage: StageInfo
  agents: AgentPresence[]
  gate_result: GateResult | null
  handoff: HandoffData | null
}
