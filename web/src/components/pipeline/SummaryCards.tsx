import { usePipelineStore } from '../../stores/pipeline'
import { formatDuration, formatTokens } from '../../utils/format'

export function SummaryCards() {
  const stages = usePipelineStore((s) => s.stages)
  const agents = usePipelineStore((s) => s.agents)

  const stageList = Object.values(stages)
  const totalTokens = Object.values(agents).reduce((sum, a) => sum + a.tokens_used, 0)
  const totalElapsed = stageList.reduce((sum, s) => sum + s.elapsed_ms, 0)
  const activeAgents = Object.values(agents).filter(
    (a) => a.state !== 'idle' && a.state !== 'done'
  ).length
  const totalAgents = Object.keys(agents).length
  const errorCount = stageList.filter((s) => s.status === 'failed').length
  const currentStage = stageList.find((s) => s.status === 'running')?.name ?? 'None'

  const cards = [
    { label: 'Total Tokens', value: formatTokens(totalTokens) },
    { label: 'Elapsed', value: formatDuration(totalElapsed) },
    { label: 'Agents', value: `${activeAgents}/${totalAgents}` },
    { label: 'Errors', value: String(errorCount), color: errorCount > 0 ? 'var(--red)' : undefined },
    { label: 'Current Stage', value: currentStage, capitalize: true },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-lg border px-4 py-3"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <div className="text-[10px] font-medium uppercase tracking-wider mb-1" style={{ color: 'var(--text-secondary)' }}>
            {card.label}
          </div>
          <div
            className={`text-lg font-semibold tabular-nums ${card.capitalize ? 'capitalize' : ''}`}
            style={{ color: card.color ?? 'var(--text-primary)' }}
          >
            {card.value}
          </div>
        </div>
      ))}
    </div>
  )
}
