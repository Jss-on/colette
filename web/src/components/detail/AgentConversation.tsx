import { usePipelineStore } from '../../stores/pipeline'
import { formatTimestamp } from '../../utils/format'

interface AgentConversationProps {
  agentId: string
}

export function AgentConversation({ agentId }: AgentConversationProps) {
  const conversation = usePipelineStore((s) => s.conversation)

  const filtered = conversation.filter((e) => e.agent_id === agentId)

  if (filtered.length === 0) {
    return (
      <div className="py-4 text-center text-xs" style={{ color: 'var(--text-secondary)' }}>
        No conversation entries
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {filtered.map((entry, i) => (
        <div key={i} className="rounded-md border px-3 py-2" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
              @{entry.display_name}
            </span>
            <span className="text-[10px] tabular-nums" style={{ color: 'var(--text-secondary)' }}>
              {formatTimestamp(entry.timestamp)}
            </span>
          </div>
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            {entry.message}
          </p>
        </div>
      ))}
    </div>
  )
}
