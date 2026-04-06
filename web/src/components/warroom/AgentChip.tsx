import type { AgentPresence } from '../../types/events'
import { statusColor } from '../../utils/colors'

interface AgentChipProps {
  agent: AgentPresence
  onClick?: () => void
}

const STATE_LABELS: Record<string, string> = {
  idle: 'Idle',
  thinking: 'Thinking',
  tool_use: 'Tool Use',
  reviewing: 'Reviewing',
  handing_off: 'Handing Off',
  done: 'Done',
  error: 'Error',
}

export function AgentChip({ agent, onClick }: AgentChipProps) {
  const color = statusColor(agent.state)
  const isActive = agent.state !== 'idle' && agent.state !== 'done'
  const isPulsing = agent.state === 'thinking'

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left transition-all"
      style={{
        background: isActive ? 'rgba(76, 215, 246, 0.04)' : 'transparent',
        opacity: agent.state === 'idle' ? 0.5 : 1,
      }}
    >
      {/* State indicator dot */}
      <span
        className={`inline-block h-2 w-2 shrink-0 rounded-full ${isPulsing ? 'animate-pulse-cyan' : ''}`}
        style={{ background: color }}
      />

      {/* Agent info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span
            className="truncate text-xs font-semibold"
            style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
          >
            @{agent.display_name}
          </span>
          <span
            className="shrink-0 text-[10px]"
            style={{ color, fontFamily: 'var(--font-label)' }}
          >
            {STATE_LABELS[agent.state] ?? agent.state}
          </span>
        </div>
        {agent.activity && isActive && (
          <p
            className="mt-0.5 truncate text-[10px]"
            style={{ color: 'var(--on-surface-variant)' }}
          >
            {agent.activity}
          </p>
        )}
      </div>
    </button>
  )
}
