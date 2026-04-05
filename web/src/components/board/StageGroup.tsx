import { motion, AnimatePresence } from 'framer-motion'
import type { AgentPresence, GateResult, StageInfo } from '../../types/events'
import type { HandoffData } from '../../types/board'
import { useUIStore } from '../../stores/ui'
import { StatusBadge } from '../shared/StatusBadge'
import { AgentRow } from './AgentRow'
import { GateFooter } from './GateFooter'
import { formatDuration } from '../../utils/format'

interface StageGroupProps {
  stage: StageInfo
  agents: AgentPresence[]
  gate: GateResult | null
  handoff: HandoffData | null
}

export function StageGroup({ stage, agents, gate }: StageGroupProps) {
  const expandedStages = useUIStore((s) => s.expandedStages)
  const toggleStage = useUIStore((s) => s.toggleStage)

  const isAutoExpanded = stage.status === 'running'
  const isExpanded = expandedStages.has(stage.name) || isAutoExpanded

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      <button
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors"
        style={{ background: 'var(--bg-surface)' }}
        onClick={() => toggleStage(stage.name)}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'var(--bg-surface-2)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'var(--bg-surface)'
        }}
      >
        <svg
          className="h-4 w-4 transition-transform"
          style={{
            color: 'var(--text-secondary)',
            transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
          }}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span className="text-sm font-semibold capitalize" style={{ color: 'var(--text-primary)' }}>
          {stage.name}
        </span>
        <StatusBadge status={stage.status} />
        <span className="ml-auto text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>
          {formatDuration(stage.elapsed_ms)}
        </span>
        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          {agents.length} agent{agents.length !== 1 ? 's' : ''}
        </span>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {agents.length > 0 ? (
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th className="px-3 py-2 text-left text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Agent</th>
                    <th className="px-3 py-2 text-left text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Status</th>
                    <th className="px-3 py-2 text-left text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Activity</th>
                    <th className="px-3 py-2 text-left text-xs font-medium hidden lg:table-cell" style={{ color: 'var(--text-secondary)' }}>Model</th>
                    <th className="px-3 py-2 text-right text-xs font-medium hidden lg:table-cell" style={{ color: 'var(--text-secondary)' }}>Tokens</th>
                    <th className="px-3 py-2 text-right text-xs font-medium hidden xl:table-cell" style={{ color: 'var(--text-secondary)' }}>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {agents.map((a) => (
                    <AgentRow key={a.agent_id} agent={a} />
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="px-4 py-3">
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  No agents in this stage
                </span>
              </div>
            )}
            {gate && <GateFooter gate={gate} stageId={stage.name} />}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
