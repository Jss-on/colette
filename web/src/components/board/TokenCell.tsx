import { formatTokens } from '../../utils/format'

interface TokenCellProps {
  tokens: number
  budget?: number
}

export function TokenCell({ tokens, budget = 100_000 }: TokenCellProps) {
  const pct = Math.min((tokens / budget) * 100, 100)

  return (
    <div className="flex items-center gap-2">
      <span
        className="text-xs font-mono tabular-nums"
        style={{ color: 'var(--text-secondary)' }}
      >
        {formatTokens(tokens)}
      </span>
      <div
        className="h-1 w-12 rounded-full overflow-hidden"
        style={{ background: 'var(--bg-surface-2)' }}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${pct}%`,
            background: pct > 80 ? 'var(--red)' : pct > 50 ? 'var(--amber)' : 'var(--accent)',
          }}
        />
      </div>
    </div>
  )
}
