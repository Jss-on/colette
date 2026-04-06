import type { DecisionEntry } from '../../stores/decisions'

interface HandoffEntryProps {
  entry: DecisionEntry
}

export function HandoffEntry({ entry }: HandoffEntryProps) {
  return (
    <div
      className="rounded-lg p-3"
      style={{
        background: 'var(--surface-container)',
        borderLeft: '3px solid var(--primary)',
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="text-[10px] tabular-nums"
          style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}
        >
          {new Date(entry.timestamp).toLocaleTimeString()}
        </span>
        <span className="text-xs" style={{ color: 'var(--primary)' }}>
          HANDOFF
        </span>
      </div>
      <p
        className="mt-1 text-xs font-medium"
        style={{ color: 'var(--on-surface)' }}
      >
        {entry.title}
      </p>
      {entry.detail && (
        <p className="mt-0.5 text-[10px]" style={{ color: 'var(--on-surface-variant)' }}>
          {entry.detail}
        </p>
      )}
    </div>
  )
}
