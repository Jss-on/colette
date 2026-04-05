import { usePipelineStore } from '../../stores/pipeline'
import { formatDuration, formatTokens } from '../../utils/format'

export function MetricsBar() {
  const stages = usePipelineStore((s) => s.stages)
  const agents = usePipelineStore((s) => s.agents)

  const stageList = Object.values(stages)
  const completed = stageList.filter((s) => s.status === 'completed').length
  const total = Math.max(stageList.length, 6)
  const progress = total > 0 ? (completed / total) * 100 : 0

  const totalTokens = Object.values(agents).reduce((sum, a) => sum + a.tokens_used, 0)
  const totalElapsed = stageList.reduce((sum, s) => sum + s.elapsed_ms, 0)
  const errorCount = stageList.filter((s) => s.status === 'failed').length
  const activeAgents = Object.values(agents).filter(
    (a) => a.state !== 'idle' && a.state !== 'done'
  ).length

  return (
    <div
      className="mb-6 flex flex-wrap items-center gap-6 rounded-lg border px-4 py-3"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      <div className="flex items-center gap-3 flex-1 min-w-[200px]">
        <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
          Progress
        </span>
        <div
          className="h-2 flex-1 rounded-full overflow-hidden"
          style={{ background: 'var(--bg-surface-2)' }}
        >
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${progress}%`, background: 'var(--green)' }}
          />
        </div>
        <span className="text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>
          {completed}/{total}
        </span>
      </div>

      <Metric label="Tokens" value={formatTokens(totalTokens)} />
      <Metric label="Elapsed" value={formatDuration(totalElapsed)} />
      <Metric label="Agents" value={`${activeAgents}/${Object.keys(agents).length}`} />
      {errorCount > 0 && <Metric label="Errors" value={String(errorCount)} color="var(--red)" />}
    </div>
  )
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
        {label}
      </span>
      <span
        className="text-sm font-medium tabular-nums"
        style={{ color: color ?? 'var(--text-primary)' }}
      >
        {value}
      </span>
    </div>
  )
}
