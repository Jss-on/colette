import { useMemo, useState } from 'react'
import { usePipelineStore } from '../../stores/pipeline'
import { StageGroup } from './StageGroup'
import { HandoffRow } from './HandoffRow'
import { BoardToolbar } from './BoardToolbar'
import type { StageGroup as StageGroupType } from '../../types/board'

const STAGE_ORDER = [
  'requirements',
  'design',
  'implementation',
  'testing',
  'deployment',
  'monitoring',
]

export function AgentBoard() {
  const stages = usePipelineStore((s) => s.stages)
  const agents = usePipelineStore((s) => s.agents)
  const [search, setSearch] = useState('')

  const groups: StageGroupType[] = useMemo(() => {
    return STAGE_ORDER.map((name) => {
      const stage = stages[name] ?? {
        name,
        status: 'pending' as const,
        elapsed_ms: 0,
        agent_count: 0,
        active_agents: [],
        gate_result: null,
      }

      const stageAgents = Object.values(agents)
        .filter((a) => a.stage === name)
        .filter(
          (a) =>
            !search ||
            a.display_name.toLowerCase().includes(search.toLowerCase()) ||
            a.state.includes(search.toLowerCase())
        )

      return {
        stage,
        agents: stageAgents,
        gate_result: stage.gate_result,
        handoff: null,
      }
    })
  }, [stages, agents, search])

  return (
    <div>
      <BoardToolbar onSearch={setSearch} />
      <div className="flex flex-col gap-3">
        {groups.map((group, i) => (
          <div key={group.stage.name}>
            {i > 0 && group.handoff && <HandoffRow handoff={group.handoff} />}
            <StageGroup
              stage={group.stage}
              agents={group.agents}
              gate={group.gate_result}
              handoff={group.handoff}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
