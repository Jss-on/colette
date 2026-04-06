import { usePipelineStore } from '../../stores/pipeline'

export function StatusFooter() {
  const agents = usePipelineStore((s) => s.agents)
  const stages = usePipelineStore((s) => s.stages)

  const totalAgents = Object.keys(agents).length
  const runningAgents = Object.values(agents).filter(
    (a) => a.state !== 'idle' && a.state !== 'done'
  ).length
  const runningStages = Object.values(stages).filter((s) => s.status === 'running').length

  return (
    <footer
      className="flex h-7 items-center justify-between px-4 text-[10px] tabular-nums"
      style={{
        background: 'var(--surface-dim)',
        borderTop: '1px solid var(--outline-variant)',
        color: 'var(--outline)',
        fontFamily: 'var(--font-mono)',
      }}
    >
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: runningStages > 0 ? 'var(--tertiary)' : 'var(--outline)' }}
          />
          {runningStages > 0 ? 'OPERATIONAL' : 'IDLE'}
        </span>
        <span>NODES: {String(totalAgents).padStart(2, '0')}</span>
        <span>ACTIVE: {String(runningAgents).padStart(2, '0')}</span>
        <span>STAGES: {Object.keys(stages).length}/6</span>
      </div>
      <div className="flex items-center gap-3">
        <span>v0.1.0</span>
      </div>
    </footer>
  )
}
