import { useUIStore } from '../../stores/ui'

const FILTER_PILLS = [
  { label: 'All', value: undefined },
  { label: 'Messages', value: 'agent_message' },
  { label: 'Handoffs', value: 'agent_handoff' },
  { label: 'Gates', value: 'gate' },
  { label: 'Approvals', value: 'approval_required' },
]

export function ActivityFilter() {
  const activityFilter = useUIStore((s) => s.activityFilter)
  const setActivityFilter = useUIStore((s) => s.setActivityFilter)

  return (
    <div className="flex gap-1.5 mb-4">
      {FILTER_PILLS.map((pill) => {
        const isActive = activityFilter.type === pill.value
        return (
          <button
            key={pill.label}
            onClick={() => setActivityFilter({ ...activityFilter, type: pill.value })}
            className="rounded-full px-3 py-1 text-xs font-medium transition-colors"
            style={{
              background: isActive ? 'var(--accent)' : 'var(--bg-surface-2)',
              color: isActive ? '#fff' : 'var(--text-secondary)',
            }}
          >
            {pill.label}
          </button>
        )
      })}
    </div>
  )
}
