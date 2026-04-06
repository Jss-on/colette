import type { GateResult } from '../../types/events'

interface GateConnectorProps {
  gate: GateResult | null
  direction: 'horizontal' | 'vertical'
}

export function GateConnector({ gate, direction }: GateConnectorProps) {
  const passed = gate?.passed
  const color = passed === true ? 'var(--tertiary)' : passed === false ? 'var(--error)' : 'var(--outline)'
  const style = passed == null ? 'dashed' : 'solid'

  if (direction === 'horizontal') {
    return (
      <div className="flex items-center px-1">
        <div
          className="h-0.5 w-6"
          style={{ background: color, borderTop: `2px ${style} ${color}` }}
        />
        {gate && (
          <div
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[8px] font-bold"
            style={{
              background: passed ? 'rgba(78, 222, 163, 0.15)' : passed === false ? 'rgba(255, 180, 171, 0.15)' : 'var(--surface-container)',
              color,
              border: `1px solid ${color}`,
            }}
          >
            {passed ? '\u2713' : passed === false ? '\u2717' : '\u2022'}
          </div>
        )}
        <div
          className="h-0.5 w-6"
          style={{ background: color, borderTop: `2px ${style} ${color}` }}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center py-1">
      <div
        className="w-0.5 h-4"
        style={{ background: color, borderLeft: `2px ${style} ${color}` }}
      />
    </div>
  )
}
