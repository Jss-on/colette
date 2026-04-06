import { useUIStore, type ActiveView } from '../../stores/ui'

const VIEWS: { key: ActiveView; label: string; shortcut: string }[] = [
  { key: 'board', label: 'Board', shortcut: 'B' },
  { key: 'pipeline', label: 'Pipeline', shortcut: 'P' },
  { key: 'activity', label: 'Activity', shortcut: 'A' },
  { key: 'artifacts', label: 'Artifacts', shortcut: 'F' },
]

export function ViewSwitcher() {
  const activeView = useUIStore((s) => s.activeView)
  const setActiveView = useUIStore((s) => s.setActiveView)

  return (
    <div
      className="flex gap-0.5 rounded-lg p-0.5"
      style={{ background: 'var(--surface-container)' }}
    >
      {VIEWS.map((v) => (
        <button
          key={v.key}
          onClick={() => setActiveView(v.key)}
          className="relative flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
          style={{
            color: activeView === v.key ? 'var(--on-surface)' : 'var(--on-surface-variant)',
            background: activeView === v.key ? 'var(--surface-container-low)' : 'transparent',
          }}
        >
          {v.label}
          <span
            className="hidden text-[10px] tabular-nums lg:inline"
            style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}
          >
            {v.shortcut}
          </span>
        </button>
      ))}
    </div>
  )
}
