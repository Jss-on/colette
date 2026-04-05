import { usePipelineStore } from '../../stores/pipeline'
import { EventType } from '../../types/events'

interface ToolCallLogProps {
  agentId: string
}

export function ToolCallLog({ agentId }: ToolCallLogProps) {
  const events = usePipelineStore((s) => s.events)

  const toolCalls = events.filter(
    (e) =>
      e.agent === agentId &&
      (e.type === EventType.AGENT_TOOL_CALL ||
        (e as unknown as Record<string, unknown>).event_type === EventType.AGENT_TOOL_CALL)
  )

  if (toolCalls.length === 0) {
    return (
      <div className="py-4 text-center text-xs" style={{ color: 'var(--text-secondary)' }}>
        No tool calls recorded
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {toolCalls.map((call, i) => {
        const detail = call.detail ?? {}
        const toolName = (detail.tool_name as string) ?? call.message ?? 'Unknown'
        const status = (detail.status as string) ?? 'running'
        const statusColor =
          status === 'success' ? 'var(--green)' : status === 'error' ? 'var(--red)' : 'var(--accent)'

        return (
          <div
            key={i}
            className="flex items-center gap-2 rounded-md border px-3 py-2"
            style={{ borderColor: 'var(--border)' }}
          >
            <span className="text-xs font-mono font-medium" style={{ color: 'var(--text-primary)' }}>
              {toolName}
            </span>
            <span
              className="ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{
                color: statusColor,
                background: `color-mix(in srgb, ${statusColor} 12%, transparent)`,
              }}
            >
              {status}
            </span>
          </div>
        )
      })}
    </div>
  )
}
