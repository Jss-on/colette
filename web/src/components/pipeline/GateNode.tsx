import type { GateResult } from '../../types/events'
import { usePipelineStore } from '../../stores/pipeline'

interface GateNodeProps {
  gate: GateResult | null
  stageName: string
}

export function GateNode({ gate }: GateNodeProps) {
  const approveGate = usePipelineStore((s) => s.approveGate)
  const rejectGate = usePipelineStore((s) => s.rejectGate)

  if (!gate) {
    return (
      <div
        className="flex h-8 w-8 items-center justify-center rounded-full border"
        style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}
      >
        <span className="text-[10px]">?</span>
      </div>
    )
  }

  const color = gate.passed ? 'var(--green)' : gate.needs_approval ? 'var(--amber)' : 'var(--red)'

  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className="flex h-8 w-8 items-center justify-center rounded-full"
        style={{
          background: `color-mix(in srgb, ${color} 15%, transparent)`,
          color,
          animation: gate.needs_approval ? 'pulse 2s infinite' : undefined,
        }}
        title={`Score: ${gate.score.toFixed(2)} — ${gate.reasons.join(', ')}`}
      >
        <span className="text-xs font-bold">
          {gate.passed ? '✓' : gate.needs_approval ? '!' : '✗'}
        </span>
      </div>
      {gate.needs_approval && (
        <div className="flex gap-1">
          <button
            onClick={() => approveGate(gate.name)}
            className="rounded px-1.5 py-0.5 text-[10px] font-medium"
            style={{ background: 'var(--green)', color: '#fff' }}
          >
            ✓
          </button>
          <button
            onClick={() => rejectGate(gate.name)}
            className="rounded px-1.5 py-0.5 text-[10px] font-medium"
            style={{ background: 'var(--red)', color: '#fff' }}
          >
            ✗
          </button>
        </div>
      )}
    </div>
  )
}
