import type { StageInfo } from '../../types/events'
import { stageStatusColor } from '../../utils/colors'
import { formatDuration } from '../../utils/format'

interface StageNodeProps {
  stage: StageInfo
  onClick: () => void
}

export function StageNode({ stage, onClick }: StageNodeProps) {
  const color = stageStatusColor(stage.status)

  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1 rounded-lg border px-4 py-3 transition-colors min-w-[120px]"
      style={{
        background: 'var(--bg-surface)',
        borderColor: stage.status === 'running' ? color : 'var(--border)',
        boxShadow: stage.status === 'running' ? `0 0 0 1px ${color}` : 'none',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--bg-surface-2)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'var(--bg-surface)'
      }}
    >
      <span className="text-xs font-semibold capitalize" style={{ color: 'var(--text-primary)' }}>
        {stage.name}
      </span>
      <span
        className="inline-flex items-center gap-1 text-[10px] font-medium"
        style={{ color }}
      >
        {stage.status === 'running' && (
          <span className="inline-block h-1.5 w-1.5 rounded-full animate-pulse" style={{ background: color }} />
        )}
        {stage.status === 'completed' && '✓ '}
        {stage.status === 'failed' && '✗ '}
        {stage.status.charAt(0).toUpperCase() + stage.status.slice(1)}
      </span>
      <span className="text-[10px] tabular-nums" style={{ color: 'var(--text-secondary)' }}>
        {formatDuration(stage.elapsed_ms)} · {stage.agent_count} agents
      </span>
    </button>
  )
}
