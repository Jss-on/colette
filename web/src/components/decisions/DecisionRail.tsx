import { useDecisionStore } from '../../stores/decisions'
import { GateEntry } from './GateEntry'
import { ApprovalEntry } from './ApprovalEntry'
import { HandoffEntry } from './HandoffEntry'
import { EscalationEntry } from './EscalationEntry'

export function DecisionRail() {
  const entries = useDecisionStore((s) => s.entries)
  const railVisible = useDecisionStore((s) => s.railVisible)
  const toggleRail = useDecisionStore((s) => s.toggleRail)
  const notificationCount = useDecisionStore((s) => s.notificationCount)
  const clearNotifications = useDecisionStore((s) => s.clearNotifications)

  if (!railVisible) {
    return (
      <button
        onClick={() => { toggleRail(); clearNotifications() }}
        className="fixed right-3 top-14 z-40 flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium shadow-lg"
        style={{
          background: 'var(--surface-container)',
          color: 'var(--on-surface-variant)',
          border: '1px solid var(--outline-variant)',
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
        Decisions
        {notificationCount > 0 && (
          <span
            className="flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-bold"
            style={{ background: 'var(--amber)', color: '#000' }}
          >
            {notificationCount}
          </span>
        )}
      </button>
    )
  }

  return (
    <aside
      className="hidden w-[320px] shrink-0 flex-col border-l overflow-y-auto lg:flex"
      style={{
        background: 'var(--surface-container-lowest)',
        borderColor: 'var(--outline-variant)',
      }}
    >
      {/* Header */}
      <div
        className="sticky top-0 z-10 flex items-center justify-between border-b px-3 py-2"
        style={{
          background: 'var(--surface-container-lowest)',
          borderColor: 'var(--outline-variant)',
        }}
      >
        <h3
          className="text-xs font-bold uppercase tracking-wider"
          style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
        >
          Decisions
        </h3>
        <button
          onClick={toggleRail}
          className="flex h-6 w-6 items-center justify-center rounded transition-colors hover:bg-white/5"
          aria-label="Collapse decision rail"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 18l6-6-6-6" />
          </svg>
        </button>
      </div>

      {/* Entries */}
      <div className="flex-1 space-y-2 p-2">
        {entries.length === 0 && (
          <p className="py-8 text-center text-xs" style={{ color: 'var(--outline)' }}>
            No decisions yet. Gate results and approvals will appear here.
          </p>
        )}
        {entries.map((entry) => {
          switch (entry.type) {
            case 'gate_passed':
            case 'gate_failed':
              return <GateEntry key={entry.id} entry={entry} />
            case 'approval_required':
              return <ApprovalEntry key={entry.id} entry={entry} />
            case 'handoff':
              return <HandoffEntry key={entry.id} entry={entry} />
            case 'escalation':
              return <EscalationEntry key={entry.id} entry={entry} />
            default:
              return null
          }
        })}
      </div>
    </aside>
  )
}
