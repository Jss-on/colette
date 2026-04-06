interface StageTokens {
  stage: string
  tokens: number
}

interface TokenChartProps {
  data: StageTokens[]
}

export function TokenChart({ data }: TokenChartProps) {
  const maxTokens = Math.max(...data.map((d) => d.tokens), 1)

  return (
    <div
      className="rounded-xl p-4"
      style={{ background: 'var(--surface-container-low)', border: '1px solid var(--outline-variant)' }}
    >
      <h3
        className="mb-3 text-xs font-bold uppercase tracking-wider"
        style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
      >
        Tokens by Stage
      </h3>
      <div className="space-y-2">
        {data.map((item) => {
          const pct = (item.tokens / maxTokens) * 100
          return (
            <div key={item.stage} className="flex items-center gap-3">
              <span
                className="w-28 shrink-0 truncate text-right text-xs capitalize"
                style={{ color: 'var(--on-surface-variant)' }}
              >
                {item.stage}
              </span>
              <div className="flex-1">
                <div
                  className="h-5 rounded"
                  style={{ background: 'var(--surface-container-highest)' }}
                >
                  <div
                    className="flex h-full items-center rounded px-2 text-[10px] font-semibold transition-all duration-500"
                    style={{
                      width: `${pct}%`,
                      minWidth: item.tokens > 0 ? '40px' : '0',
                      background: 'var(--primary)',
                      color: 'var(--on-primary)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {item.tokens > 0 ? item.tokens.toLocaleString() : ''}
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
