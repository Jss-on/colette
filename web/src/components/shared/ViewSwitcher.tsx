import { useUIStore, type ActiveView } from '../../stores/ui'

const VIEWS: { key: ActiveView; label: string }[] = [
  { key: 'board', label: 'Board' },
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'activity', label: 'Activity' },
  { key: 'artifacts', label: 'Artifacts' },
]

export function ViewSwitcher() {
  const activeView = useUIStore((s) => s.activeView)
  const setActiveView = useUIStore((s) => s.setActiveView)

  return (
    <div className="flex gap-1 rounded-lg p-1" style={{ background: 'var(--bg-surface-2)' }}>
      {VIEWS.map((v) => (
        <button
          key={v.key}
          onClick={() => setActiveView(v.key)}
          className="relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors"
          style={{
            color: activeView === v.key ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: activeView === v.key ? 'var(--bg-surface)' : 'transparent',
          }}
        >
          {v.label}
        </button>
      ))}
    </div>
  )
}
