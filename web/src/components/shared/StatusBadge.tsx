import type { StageStatus } from '../../types/events'
import { stageStatusColor } from '../../utils/colors'

interface StatusBadgeProps {
  status: StageStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const color = stageStatusColor(status)
  const label = status.charAt(0).toUpperCase() + status.slice(1)

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{
        color,
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
      }}
    >
      {status === 'running' && (
        <span
          className="inline-block h-1.5 w-1.5 rounded-full animate-pulse"
          style={{ background: color }}
        />
      )}
      {label}
    </span>
  )
}
