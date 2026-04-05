import type { AgentPresence } from '../../types/events'
import { useUIStore } from '../../stores/ui'
import { StatusCell } from './StatusCell'
import { ActivityCell } from './ActivityCell'
import { ModelCell } from './ModelCell'
import { TokenCell } from './TokenCell'
import { DurationCell } from './DurationCell'

interface AgentRowProps {
  agent: AgentPresence
}

export function AgentRow({ agent }: AgentRowProps) {
  const selectAgent = useUIStore((s) => s.selectAgent)
  const isRunning = agent.state !== 'idle' && agent.state !== 'done' && agent.state !== 'error'

  const elapsed = agent.started_at
    ? Date.now() - new Date(agent.started_at).getTime()
    : 0

  return (
    <tr
      className="cursor-pointer transition-colors"
      style={{ borderBottom: '1px solid var(--border)' }}
      onClick={() => selectAgent(agent.agent_id)}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--bg-hover)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
      }}
    >
      <td className="px-3 py-2">
        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          @{agent.display_name}
        </span>
      </td>
      <td className="px-3 py-2">
        <StatusCell state={agent.state} />
      </td>
      <td className="px-3 py-2">
        <ActivityCell activity={agent.activity} />
      </td>
      <td className="px-3 py-2 hidden lg:table-cell">
        <ModelCell model={agent.model} />
      </td>
      <td className="px-3 py-2 hidden lg:table-cell text-right">
        <TokenCell tokens={agent.tokens_used} />
      </td>
      <td className="px-3 py-2 hidden xl:table-cell text-right">
        <DurationCell startedAt={agent.started_at} elapsed={elapsed} running={isRunning} />
      </td>
    </tr>
  )
}
