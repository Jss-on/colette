import { usePipelineStore } from '../../stores/pipeline'
import { ApprovalCard } from './ApprovalCard'

export function ApprovalQueue() {
  const approvals = usePipelineStore((s) => s.approvals)

  const pending = approvals.filter((a) => a.id)

  return (
    <div
      className="rounded-lg border p-4"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          Pending Approvals
        </h3>
        {pending.length > 0 && (
          <span
            className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
            style={{ background: 'var(--red)', color: '#fff' }}
          >
            {pending.length}
          </span>
        )}
      </div>

      {pending.length === 0 ? (
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          No approvals pending
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {pending.map((a) => (
            <ApprovalCard key={a.id} approval={a} />
          ))}
        </div>
      )}
    </div>
  )
}
