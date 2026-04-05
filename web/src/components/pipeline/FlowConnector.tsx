import type { StageStatus } from '../../types/events'

interface FlowConnectorProps {
  status: StageStatus
}

export function FlowConnector({ status }: FlowConnectorProps) {
  const color =
    status === 'completed'
      ? 'var(--green)'
      : status === 'running'
        ? 'var(--accent)'
        : 'var(--border)'

  return (
    <div className="flex items-center mx-1" style={{ width: '32px' }}>
      <div
        className="h-0.5 w-full"
        style={{
          background: color,
          ...(status === 'pending'
            ? { backgroundImage: `repeating-linear-gradient(90deg, ${color} 0, ${color} 4px, transparent 4px, transparent 8px)` }
            : {}),
        }}
      />
      <svg className="h-3 w-3 -ml-1 flex-shrink-0" fill={color} viewBox="0 0 12 12">
        <path d="M4 2l6 4-6 4V2z" />
      </svg>
    </div>
  )
}
