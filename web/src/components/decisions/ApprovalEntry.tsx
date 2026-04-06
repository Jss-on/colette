import type { DecisionEntry } from '../../stores/decisions'
import { usePipelineStore } from '../../stores/pipeline'
import { useDecisionStore } from '../../stores/decisions'

interface ApprovalEntryProps {
  entry: DecisionEntry
}

export function ApprovalEntry({ entry }: ApprovalEntryProps) {
  const approveGate = usePipelineStore((s) => s.approveGate)
  const rejectGate = usePipelineStore((s) => s.rejectGate)
  const resolveEntry = useDecisionStore((s) => s.resolveEntry)

  const handleApprove = async () => {
    if (entry.approvalId) {
      await approveGate(entry.approvalId)
      resolveEntry(entry.id)
    }
  }

  const handleReject = async () => {
    if (entry.approvalId) {
      await rejectGate(entry.approvalId)
      resolveEntry(entry.id)
    }
  }

  return (
    <div
      className={`rounded-lg p-3 ${!entry.resolved ? 'animate-pulse-cyan' : ''}`}
      style={{
        background: 'var(--surface-container)',
        borderLeft: '3px solid var(--amber)',
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="text-[10px] tabular-nums"
          style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}
        >
          {new Date(entry.timestamp).toLocaleTimeString()}
        </span>
        <span
          className="text-xs font-semibold uppercase"
          style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
        >
          {entry.stage} Gate
        </span>
        {!entry.resolved && (
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
            style={{ background: 'rgba(210, 153, 34, 0.15)', color: 'var(--amber)' }}
          >
            NEEDS APPROVAL
          </span>
        )}
      </div>

      <p className="mt-1 text-xs" style={{ color: 'var(--on-surface-variant)' }}>
        {entry.detail}
      </p>

      {entry.score != null && (
        <span
          className="mt-1 block text-[10px] tabular-nums"
          style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
        >
          Score: {Math.round(entry.score * 100)}%
          {entry.threshold != null && ` / Threshold: ${Math.round(entry.threshold * 100)}%`}
        </span>
      )}

      {!entry.resolved && (
        <div className="mt-2 flex gap-2">
          <button
            onClick={handleApprove}
            className="rounded-md px-3 py-1 text-xs font-medium transition-colors"
            style={{ background: 'var(--tertiary-container)', color: '#fff' }}
          >
            Approve
          </button>
          <button
            onClick={handleReject}
            className="rounded-md px-3 py-1 text-xs font-medium transition-colors"
            style={{ background: 'var(--error-container)', color: '#fff' }}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  )
}
