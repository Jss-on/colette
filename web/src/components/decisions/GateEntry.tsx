import { useState } from 'react'
import type { DecisionEntry } from '../../stores/decisions'

interface GateEntryProps {
  entry: DecisionEntry
}

export function GateEntry({ entry }: GateEntryProps) {
  const [expanded, setExpanded] = useState(false)
  const passed = entry.type === 'gate_passed'

  return (
    <div
      className="rounded-lg p-3"
      style={{
        background: 'var(--surface-container)',
        borderLeft: `3px solid ${passed ? 'var(--tertiary)' : 'var(--error)'}`,
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
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
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span
              className="text-xs font-semibold"
              style={{ color: passed ? 'var(--tertiary)' : 'var(--error)' }}
            >
              {passed ? 'PASSED' : 'FAILED'}
            </span>
            {entry.score != null && (
              <span
                className="text-[10px] tabular-nums"
                style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
              >
                {Math.round(entry.score * 100)}%
                {entry.threshold != null && ` (threshold: ${Math.round(entry.threshold * 100)}%)`}
              </span>
            )}
          </div>
        </div>
        {entry.reasons && entry.reasons.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="shrink-0 text-[10px]"
            style={{ color: 'var(--primary)' }}
          >
            {expanded ? 'Hide' : 'Details'}
          </button>
        )}
      </div>
      {expanded && entry.reasons && (
        <ul className="mt-2 space-y-0.5">
          {entry.reasons.map((r, i) => (
            <li key={i} className="text-[10px]" style={{ color: 'var(--on-surface-variant)' }}>
              {r}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
