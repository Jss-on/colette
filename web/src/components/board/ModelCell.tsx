import type { ModelTier } from '../../types/events'
import { TierBadge } from '../shared/TierBadge'

interface ModelCellProps {
  model: string
}

function inferTier(model: string): ModelTier | null {
  const lower = model.toLowerCase()
  if (lower.includes('opus')) return 'PLANNING'
  if (lower.includes('sonnet')) return 'EXECUTION'
  if (lower.includes('haiku')) return 'VALIDATION'
  return null
}

export function ModelCell({ model }: ModelCellProps) {
  const tier = inferTier(model)

  if (!model) {
    return <span style={{ color: 'var(--text-secondary)' }}>—</span>
  }

  return (
    <div className="flex items-center gap-2">
      <span
        className="text-xs font-mono truncate"
        style={{ color: 'var(--text-secondary)' }}
      >
        {model}
      </span>
      {tier && <TierBadge tier={tier} />}
    </div>
  )
}
