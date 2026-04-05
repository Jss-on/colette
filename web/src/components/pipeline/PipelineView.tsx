import { usePipelineStore } from '../../stores/pipeline'
import { useUIStore } from '../../stores/ui'
import { StageNode } from './StageNode'
import { GateNode } from './GateNode'
import { FlowConnector } from './FlowConnector'
import { GanttTimeline } from './GanttTimeline'
import { SummaryCards } from './SummaryCards'
import type { StageInfo } from '../../types/events'

const STAGE_ORDER = [
  'requirements',
  'design',
  'implementation',
  'testing',
  'deployment',
  'monitoring',
]

export function PipelineView() {
  const stages = usePipelineStore((s) => s.stages)
  const setActiveView = useUIStore((s) => s.setActiveView)
  const toggleStage = useUIStore((s) => s.toggleStage)

  const stageList: StageInfo[] = STAGE_ORDER.map((name) => stages[name] ?? {
    name,
    status: 'pending' as const,
    elapsed_ms: 0,
    agent_count: 0,
    active_agents: [],
    gate_result: null,
  })

  const handleStageClick = (name: string) => {
    setActiveView('board')
    toggleStage(name)
  }

  return (
    <div>
      <SummaryCards />

      <div
        className="mb-6 rounded-lg border p-6 overflow-x-auto"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
      >
        <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
          Pipeline Flow
        </h3>
        <div className="flex items-center justify-center min-w-max">
          {stageList.map((stage, i) => (
            <div key={stage.name} className="flex items-center">
              <StageNode stage={stage} onClick={() => handleStageClick(stage.name)} />
              {i < stageList.length - 1 && (
                <>
                  <FlowConnector status={stage.status} />
                  <GateNode gate={stage.gate_result} stageName={stage.name} />
                  <FlowConnector status={stageList[i + 1].status} />
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      <GanttTimeline stages={stageList} />
    </div>
  )
}
