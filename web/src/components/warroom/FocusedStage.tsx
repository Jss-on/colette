import { motion } from 'framer-motion'
import type { AgentPresence, StageInfo } from '../../types/events'
import { AgentChip } from './AgentChip'
import { formatDuration } from '../../utils/format'
import { stageStatusColor } from '../../utils/colors'

interface FocusedStageProps {
  stage: StageInfo
  agents: AgentPresence[]
  onClose: () => void
  onAgentClick?: (agentId: string) => void
}

export function FocusedStage({ stage, agents, onClose, onAgentClick }: FocusedStageProps) {
  const color = stageStatusColor(stage.status)

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="glass-card rounded-xl p-6"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2
            className="text-lg font-bold capitalize"
            style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
          >
            {stage.name}
          </h2>
          <span
            className="rounded px-2 py-0.5 text-xs font-semibold uppercase"
            style={{ background: `${color}15`, color }}
          >
            {stage.status}
          </span>
          {stage.elapsed_ms > 0 && (
            <span
              className="text-xs tabular-nums"
              style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}
            >
              {formatDuration(stage.elapsed_ms)}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-white/5"
          aria-label="Close focused stage"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Gate result */}
      {stage.gate_result && (
        <div
          className="mb-4 rounded-lg p-3"
          style={{
            background: stage.gate_result.passed
              ? 'rgba(78, 222, 163, 0.06)'
              : 'rgba(255, 180, 171, 0.06)',
            border: `1px solid ${stage.gate_result.passed ? 'rgba(78, 222, 163, 0.2)' : 'rgba(255, 180, 171, 0.2)'}`,
          }}
        >
          <div className="flex items-center gap-2 text-sm font-semibold">
            <span style={{ color: stage.gate_result.passed ? 'var(--tertiary)' : 'var(--error)' }}>
              Gate: {stage.gate_result.passed ? 'PASSED' : 'FAILED'}
            </span>
            <span style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}>
              {Math.round(stage.gate_result.score * 100)}%
            </span>
          </div>
          {stage.gate_result.reasons.length > 0 && (
            <ul className="mt-2 space-y-1">
              {stage.gate_result.reasons.map((reason, i) => (
                <li key={i} className="text-xs" style={{ color: 'var(--on-surface-variant)' }}>
                  {reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Agent grid */}
      <div className="grid gap-2 sm:grid-cols-2">
        {agents.map((agent) => (
          <div key={agent.agent_id} className="rounded-lg p-1" style={{ background: 'var(--surface-container)' }}>
            <AgentChip agent={agent} onClick={() => onAgentClick?.(agent.agent_id)} />
          </div>
        ))}
        {agents.length === 0 && (
          <p className="col-span-2 py-4 text-center text-sm" style={{ color: 'var(--outline)' }}>
            No agents assigned to this stage
          </p>
        )}
      </div>
    </motion.div>
  )
}
