interface RunSummary {
  id: string
  status: string
  current_stage: string
  total_tokens: number
  started_at: string
  completed_at: string | null
  duration_seconds: number
}

interface RunCardProps {
  run: RunSummary
  onClick: () => void
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'var(--tertiary)',
  running: 'var(--primary)',
  failed: 'var(--error)',
  cancelled: 'var(--amber)',
}

export function RunCard({ run, onClick }: RunCardProps) {
  const color = STATUS_COLORS[run.status] ?? 'var(--outline)'

  return (
    <button
      onClick={onClick}
      className="glass-card flex w-full flex-col gap-2 rounded-xl p-4 text-left transition-all"
    >
      <div className="flex items-center justify-between">
        <span
          className="text-xs font-semibold uppercase"
          style={{ color, fontFamily: 'var(--font-label)' }}
        >
          {run.status}
        </span>
        <span
          className="text-[10px] tabular-nums"
          style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}
        >
          {new Date(run.started_at).toLocaleString()}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <Stat label="Stage" value={run.current_stage} />
        <Stat label="Tokens" value={run.total_tokens.toLocaleString()} />
        <Stat label="Duration" value={`${Math.round(run.duration_seconds)}s`} />
      </div>

      {/* Mini stage progress */}
      <div className="flex gap-0.5">
        {['requirements', 'design', 'implementation', 'testing', 'deployment', 'monitoring'].map(
          (stage) => (
            <div
              key={stage}
              className="h-1 flex-1 rounded-full"
              style={{
                background:
                  run.status === 'completed' ? 'var(--tertiary)' :
                  stage === run.current_stage ? 'var(--primary)' :
                  'var(--surface-container-highest)',
              }}
            />
          ),
        )}
      </div>
    </button>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span
        className="block text-[10px] uppercase tracking-wider"
        style={{ color: 'var(--outline)', fontFamily: 'var(--font-label)' }}
      >
        {label}
      </span>
      <span
        className="text-xs"
        style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
      >
        {value}
      </span>
    </div>
  )
}
