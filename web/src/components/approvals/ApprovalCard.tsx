import { useState } from 'react'
import type { ApprovalRequest } from '../../types/events'
import { usePipelineStore } from '../../stores/pipeline'

interface ApprovalCardProps {
  approval: ApprovalRequest
}

export function ApprovalCard({ approval }: ApprovalCardProps) {
  const approveGate = usePipelineStore((s) => s.approveGate)
  const rejectGate = usePipelineStore((s) => s.rejectGate)
  const [expanded, setExpanded] = useState(false)

  const riskColor =
    approval.risk_level === 'high'
      ? 'var(--red)'
      : approval.risk_level === 'medium'
        ? 'var(--amber)'
        : 'var(--green)'

  return (
    <div
      className="rounded-lg border-l-2 border border-l-[var(--purple)] overflow-hidden"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', borderLeftColor: 'var(--purple)' }}
    >
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
            {approval.gate_name}
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-medium capitalize"
            style={{ background: 'var(--bg-surface-2)', color: 'var(--text-secondary)' }}
          >
            {approval.stage}
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-medium capitalize"
            style={{
              color: riskColor,
              background: `color-mix(in srgb, ${riskColor} 12%, transparent)`,
            }}
          >
            {approval.risk_level} risk
          </span>
        </div>

        <p className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>
          {approval.reason}
        </p>

        <div className="flex items-center gap-3 mb-2">
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            Score: <span className="font-mono tabular-nums">{approval.score.toFixed(2)}</span>
          </span>
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            Threshold: <span className="font-mono tabular-nums">{approval.threshold.toFixed(2)}</span>
          </span>
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] mb-3"
          style={{ color: 'var(--accent)' }}
        >
          {expanded ? 'Hide context' : 'Show context'}
        </button>

        <div className="flex gap-2">
          <button
            onClick={() => approveGate(approval.id)}
            className="rounded px-3 py-1 text-xs font-medium transition-colors"
            style={{ background: 'var(--green)', color: '#fff' }}
          >
            Approve
          </button>
          <button
            onClick={() => rejectGate(approval.id)}
            className="rounded px-3 py-1 text-xs font-medium transition-colors"
            style={{ background: 'var(--red)', color: '#fff' }}
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  )
}
