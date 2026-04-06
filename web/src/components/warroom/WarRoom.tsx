import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { usePipelineStore } from '../../stores/pipeline'
import { useUIStore } from '../../stores/ui'
import type { StageInfo } from '../../types/events'
import { StageRoom } from './StageRoom'
import { GateConnector } from './GateConnector'
import { FocusedStage } from './FocusedStage'

const STAGE_ORDER = ['requirements', 'design', 'implementation', 'testing', 'deployment', 'monitoring']

const DEFAULT_STAGE: StageInfo = {
  name: '',
  status: 'pending',
  elapsed_ms: 0,
  agent_count: 0,
  active_agents: [],
  gate_result: null,
}

export function WarRoom() {
  const stages = usePipelineStore((s) => s.stages)
  const agents = usePipelineStore((s) => s.agents)
  const selectAgent = useUIStore((s) => s.selectAgent)
  const [focusedStage, setFocusedStage] = useState<string | null>(null)

  const getStage = (name: string): StageInfo => stages[name] ?? { ...DEFAULT_STAGE, name }

  const getAgentsForStage = (stageName: string) =>
    Object.values(agents).filter((a) => a.stage === stageName)

  // Get gate between two stages (gate belongs to the preceding stage)
  const getGateBetween = (from: string) => stages[from]?.gate_result ?? null

  const focused = focusedStage ? getStage(focusedStage) : null

  return (
    <div>
      <AnimatePresence mode="wait">
        {focused ? (
          <FocusedStage
            key={focused.name}
            stage={focused}
            agents={getAgentsForStage(focused.name)}
            onClose={() => setFocusedStage(null)}
            onAgentClick={selectAgent}
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-3">
            {/* Row 1: Requirements -> Design -> Implementation */}
            {STAGE_ORDER.slice(0, 3).map((name, i) => (
              <div key={name} className="flex items-stretch gap-0">
                <div className="flex-1">
                  <StageRoom
                    stage={getStage(name)}
                    agents={getAgentsForStage(name)}
                    onAgentClick={selectAgent}
                    onExpand={() => setFocusedStage(name)}
                  />
                </div>
                {i < 2 && (
                  <div className="hidden items-center md:flex">
                    <GateConnector gate={getGateBetween(name)} direction="horizontal" />
                  </div>
                )}
              </div>
            ))}

            {/* Row 2: Testing -> Deployment -> Monitoring */}
            {STAGE_ORDER.slice(3).map((name, i) => (
              <div key={name} className="flex items-stretch gap-0">
                <div className="flex-1">
                  <StageRoom
                    stage={getStage(name)}
                    agents={getAgentsForStage(name)}
                    onAgentClick={selectAgent}
                    onExpand={() => setFocusedStage(name)}
                  />
                </div>
                {i < 2 && (
                  <div className="hidden items-center md:flex">
                    <GateConnector gate={getGateBetween(name)} direction="horizontal" />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}
