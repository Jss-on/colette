import type { ModelTier } from '../../types/events'
import { tierColor } from '../../utils/colors'

interface TierBadgeProps {
  tier: ModelTier
}

export function TierBadge({ tier }: TierBadgeProps) {
  const color = tierColor(tier)
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
      style={{
        color,
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
      }}
    >
      {tier}
    </span>
  )
}
