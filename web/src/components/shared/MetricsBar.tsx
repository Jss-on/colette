import { usePipelineStore } from '../../stores/pipeline'
import { formatDuration, formatTokens } from '../../utils/format'

const STAGE_ORDER = ['requirements', 'design', 'implementation', 'testing', 'deployment', 'monitoring']

export function MetricsBar() {
  const stages = usePipelineStore((s) => s.stages)
  const agents = usePipelineStore((s) => s.agents)

  const stageList = Object.values(stages)
  const completed = stageList.filter((s) => s.status === 'completed').length
  const total = 6
  const progress = (completed / total) * 100

  const totalTokens = Object.values(agents).reduce((sum, a) => sum + a.tokens_used, 0)
  const totalElapsed = stageList.reduce((sum, s) => sum + s.elapsed_ms, 0)
  const errorCount = stageList.filter((s) => s.status === 'failed').length
  const activeAgents = Object.values(agents).filter(
    (a) => a.state !== 'idle' && a.state !== 'done'
  ).length

  // Find current running stage
  const currentStage = stageList.find((s) => s.status === 'running')

  // Estimate cost: rough token pricing
  const costEstimate = (totalTokens / 1_000_000) * 3

  return (
    <div
      className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border px-4 py-2.5"
      style={{
        background: 'var(--surface-container-low)',
        borderColor: 'var(--outline-variant)',
      }}
    >
      {/* Segmented progress bar */}
      <div className="flex items-center gap-2 flex-1 min-w-[200px]">
        <span
          className="text-[10px] font-medium uppercase tracking-wider"
          style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-label)' }}
        >
          Pipeline
        </span>
        <div className="flex flex-1 gap-0.5">
          {STAGE_ORDER.map((name) => {
            const stage = stages[name]
            const status = stage?.status ?? 'pending'
            return (
              <div
                key={name}
                className="h-1.5 flex-1 rounded-full transition-all duration-500"
                title={`${name}: ${status}`}
                style={{
                  background:
                    status === 'completed' ? 'var(--tertiary)' :
                    status === 'running' ? 'var(--primary)' :
                    status === 'failed' ? 'var(--error)' :
                    'var(--surface-container-highest)',
                }}
              />
            )
          })}
        </div>
        <span
          className="text-[10px] tabular-nums"
          style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
        >
          {Math.round(progress)}%
        </span>
      </div>

      {/* Current stage badge */}
      {currentStage && (
        <span
          className="flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
          style={{
            background: 'rgba(76, 215, 246, 0.1)',
            color: 'var(--primary)',
            fontFamily: 'var(--font-label)',
          }}
        >
          <span
            className="inline-block h-1.5 w-1.5 rounded-full animate-pulse-cyan"
            style={{ background: 'var(--primary)' }}
          />
          {currentStage.name}
        </span>
      )}

      <Metric label="Tokens" value={formatTokens(totalTokens)} />
      <Metric label="Elapsed" value={formatDuration(totalElapsed)} />
      <Metric label="Cost" value={`~$${costEstimate.toFixed(2)}`} />
      <Metric label="Agents" value={`${activeAgents}/${Object.keys(agents).length}`} />
      {errorCount > 0 && <Metric label="Errors" value={String(errorCount)} color="var(--error)" />}
    </div>
  )
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className="text-[10px] uppercase tracking-wider"
        style={{ color: 'var(--outline)', fontFamily: 'var(--font-label)' }}
      >
        {label}
      </span>
      <span
        className="text-xs font-medium tabular-nums"
        style={{
          color: color ?? 'var(--on-surface)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        {value}
      </span>
    </div>
  )
}
