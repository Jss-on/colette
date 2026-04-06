import type { AgentPresence, StageInfo } from '../../types/events'
import { stageStatusColor } from '../../utils/colors'
import { AgentChip } from './AgentChip'
import { formatDuration } from '../../utils/format'

interface StageRoomProps {
  stage: StageInfo
  agents: AgentPresence[]
  onAgentClick?: (agentId: string) => void
  onExpand?: () => void
}

const STAGE_ICONS: Record<string, string> = {
  requirements: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
  design: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  implementation: 'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4',
  testing: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  deployment: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
  monitoring: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
}

export function StageRoom({ stage, agents, onAgentClick, onExpand }: StageRoomProps) {
  const color = stageStatusColor(stage.status)
  const isRunning = stage.status === 'running'
  const isCompleted = stage.status === 'completed'

  return (
    <div
      onClick={onExpand}
      className={`glass-card flex flex-col rounded-xl p-3 transition-all cursor-pointer ${isRunning ? 'glow-cyan' : ''}`}
      style={{
        borderColor: isRunning ? 'rgba(76, 215, 246, 0.3)' : undefined,
      }}
    >
      {/* Header */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke={color}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d={STAGE_ICONS[stage.name] ?? STAGE_ICONS.requirements} />
          </svg>
          <h3
            className="text-sm font-bold capitalize"
            style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
          >
            {stage.name}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
            style={{
              background: `${color}15`,
              color,
              fontFamily: 'var(--font-label)',
            }}
          >
            {STATUS_LABELS[stage.status] ?? stage.status}
          </span>
        </div>
      </div>

      {/* Duration */}
      {(isRunning || isCompleted) && stage.elapsed_ms > 0 && (
        <span
          className="mb-2 text-[10px] tabular-nums"
          style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}
        >
          {formatDuration(stage.elapsed_ms)}
        </span>
      )}

      {/* Agents */}
      <div className="flex flex-1 flex-col gap-0.5">
        {agents.length > 0 ? (
          agents.map((agent) => (
            <AgentChip
              key={agent.agent_id}
              agent={agent}
              onClick={() => onAgentClick?.(agent.agent_id)}
            />
          ))
        ) : (
          <span className="py-2 text-center text-[10px]" style={{ color: 'var(--outline)' }}>
            No agents
          </span>
        )}
      </div>

      {/* Gate result */}
      {stage.gate_result && (
        <div
          className="mt-2 flex items-center gap-2 rounded-lg px-2 py-1.5 text-[10px]"
          style={{
            background: stage.gate_result.passed
              ? 'rgba(78, 222, 163, 0.08)'
              : 'rgba(255, 180, 171, 0.08)',
            borderLeft: `3px solid ${stage.gate_result.passed ? 'var(--tertiary)' : 'var(--error)'}`,
          }}
        >
          <span
            className="font-semibold"
            style={{ color: stage.gate_result.passed ? 'var(--tertiary)' : 'var(--error)' }}
          >
            Gate: {stage.gate_result.passed ? 'PASSED' : 'FAILED'}
          </span>
          <span style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}>
            {Math.round(stage.gate_result.score * 100)}%
          </span>
        </div>
      )}
    </div>
  )
}
