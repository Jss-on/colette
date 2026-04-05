import type { GateResult } from '../../types/events'
import { usePipelineStore } from '../../stores/pipeline'

interface GateFooterProps {
  gate: GateResult
  stageId: string
}

export function GateFooter({ gate }: GateFooterProps) {
  const approveGate = usePipelineStore((s) => s.approveGate)
  const rejectGate = usePipelineStore((s) => s.rejectGate)

  const color = gate.passed ? 'var(--green)' : gate.needs_approval ? 'var(--amber)' : 'var(--red)'

  return (
    <div
      className="flex items-center gap-3 border-t px-4 py-2"
      style={{ borderTopColor: 'var(--border)' }}
    >
      <span
        className="inline-flex h-5 w-5 items-center justify-center rounded-full text-xs"
        style={{
          background: `color-mix(in srgb, ${color} 15%, transparent)`,
          color,
        }}
      >
        {gate.passed ? '✓' : gate.needs_approval ? '!' : '✗'}
      </span>
      <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
        {gate.name}
      </span>
      <span className="text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>
        Score: {gate.score.toFixed(2)}
      </span>
      {gate.needs_approval && (
        <div className="ml-auto flex gap-2">
          <button
            onClick={() => approveGate(gate.name)}
            className="rounded px-2 py-0.5 text-xs font-medium transition-colors"
            style={{ background: 'var(--green)', color: '#fff' }}
          >
            Approve
          </button>
          <button
            onClick={() => rejectGate(gate.name)}
            className="rounded px-2 py-0.5 text-xs font-medium transition-colors"
            style={{ background: 'var(--red)', color: '#fff' }}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  )
}
