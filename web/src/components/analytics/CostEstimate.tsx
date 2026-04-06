interface CostEstimateProps {
  totalTokens: number
  modelPricing?: number
}

export function CostEstimate({ totalTokens, modelPricing = 3 }: CostEstimateProps) {
  const cost = (totalTokens / 1_000_000) * modelPricing

  return (
    <div
      className="rounded-xl p-4"
      style={{ background: 'var(--surface-container-low)', border: '1px solid var(--outline-variant)' }}
    >
      <h3
        className="mb-1 text-xs font-bold uppercase tracking-wider"
        style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
      >
        Cost Estimate
      </h3>
      <div className="flex items-baseline gap-1">
        <span
          className="text-2xl font-bold tabular-nums"
          style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)' }}
        >
          ${cost.toFixed(2)}
        </span>
        <span className="text-xs" style={{ color: 'var(--outline)' }}>
          USD
        </span>
      </div>
      <p className="mt-1 text-[10px]" style={{ color: 'var(--outline)' }}>
        Based on {totalTokens.toLocaleString()} tokens @ ${modelPricing}/M tokens
      </p>
    </div>
  )
}
