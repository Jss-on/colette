import type { HandoffData } from '../../types/board'

interface HandoffRowProps {
  handoff: HandoffData
}

export function HandoffRow({ handoff }: HandoffRowProps) {
  return (
    <div
      className="mx-4 my-2 flex items-center gap-3 rounded-md border-l-2 px-4 py-2"
      style={{
        background: 'rgba(47, 129, 247, 0.04)',
        borderLeftColor: 'var(--accent)',
      }}
    >
      <svg
        className="h-4 w-4 flex-shrink-0"
        style={{ color: 'var(--accent)' }}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
      </svg>
      <span className="text-xs" style={{ color: 'var(--accent)' }}>
        Handoff: {handoff.from_stage} → {handoff.to_stage}
      </span>
      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
        {handoff.stories_count} stories · {handoff.nfrs_count} NFRs · Score: {handoff.score.toFixed(2)}
      </span>
    </div>
  )
}
