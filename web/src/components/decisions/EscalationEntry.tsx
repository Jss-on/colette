import type { DecisionEntry } from '../../stores/decisions'

interface EscalationEntryProps {
  entry: DecisionEntry
}

export function EscalationEntry({ entry }: EscalationEntryProps) {
  return (
    <div
      className="rounded-lg p-3"
      style={{
        background: 'var(--surface-container)',
        borderLeft: '3px solid var(--secondary)',
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="text-[10px] tabular-nums"
          style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}
        >
          {new Date(entry.timestamp).toLocaleTimeString()}
        </span>
        <span className="text-xs font-semibold" style={{ color: 'var(--secondary)' }}>
          ESCALATION
        </span>
      </div>
      <p className="mt-1 text-xs" style={{ color: 'var(--on-surface)' }}>
        {entry.title}
      </p>
      {entry.detail && (
        <p className="mt-0.5 text-[10px]" style={{ color: 'var(--on-surface-variant)' }}>
          {entry.detail}
        </p>
      )}
      {!entry.resolved && (
        <div className="mt-2 flex gap-2">
          <button
            className="rounded-md px-3 py-1 text-xs font-medium"
            style={{ background: 'var(--surface-container-high)', color: 'var(--on-surface)' }}
          >
            Acknowledge
          </button>
        </div>
      )}
    </div>
  )
}
