import { formatDuration } from '../../utils/format'

interface DurationCellProps {
  startedAt: string
  elapsed?: number
  running: boolean
}

export function DurationCell({ elapsed = 0, running }: DurationCellProps) {
  return (
    <span
      className="text-xs font-mono tabular-nums"
      style={{ color: running ? 'var(--accent)' : 'var(--text-secondary)' }}
    >
      {formatDuration(elapsed)}
    </span>
  )
}
