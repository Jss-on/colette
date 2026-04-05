import type { PipelineEvent } from '../../types/events'
import { EventType } from '../../types/events'
import { formatTimestamp } from '../../utils/format'

interface ActivityEntryProps {
  event: PipelineEvent
}

function getEntryStyle(event: PipelineEvent): { borderColor: string; bg: string } {
  const eventType = event.type ?? (event as unknown as Record<string, unknown>).event_type
  if (eventType === EventType.AGENT_HANDOFF)
    return { borderColor: 'var(--accent)', bg: 'rgba(47,129,247,0.04)' }
  if (eventType === EventType.GATE_PASSED)
    return { borderColor: 'var(--green)', bg: 'rgba(63,185,80,0.04)' }
  if (eventType === EventType.GATE_FAILED)
    return { borderColor: 'var(--red)', bg: 'rgba(248,81,73,0.04)' }
  if (eventType === EventType.APPROVAL_REQUIRED)
    return { borderColor: 'var(--purple)', bg: 'rgba(163,113,247,0.04)' }
  return { borderColor: 'transparent', bg: 'transparent' }
}

export function ActivityEntry({ event }: ActivityEntryProps) {
  const style = getEntryStyle(event)
  const agentName = event.agent ?? 'System'

  return (
    <div
      className="flex gap-3 rounded-md border-l-2 px-3 py-2"
      style={{ borderLeftColor: style.borderColor, background: style.bg }}
    >
      <div
        className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
        style={{ background: 'var(--bg-surface-2)', color: 'var(--text-primary)' }}
      >
        {agentName.charAt(0).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
            @{agentName}
          </span>
          {event.stage && (
            <span
              className="rounded px-1 py-0.5 text-[10px] capitalize"
              style={{ background: 'var(--bg-surface-2)', color: 'var(--text-secondary)' }}
            >
              {event.stage}
            </span>
          )}
          <span className="ml-auto text-[10px] tabular-nums" style={{ color: 'var(--text-secondary)' }}>
            {formatTimestamp(event.timestamp)}
          </span>
        </div>
        <p className="mt-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
          {event.message || String(event.type ?? (event as unknown as Record<string, unknown>).event_type)}
        </p>
      </div>
    </div>
  )
}
