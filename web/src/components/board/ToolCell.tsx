import type { ToolCall } from '../../types/events'

interface ToolCellProps {
  tools: ToolCall[]
}

export function ToolCell({ tools }: ToolCellProps) {
  if (tools.length === 0) {
    return (
      <span className="text-xs" style={{ color: 'var(--outline)' }}>
        --
      </span>
    )
  }

  const lastTool = tools[tools.length - 1]
  const statusColor =
    lastTool.status === 'success' ? 'var(--tertiary)' :
    lastTool.status === 'error' ? 'var(--error)' :
    'var(--primary)'

  return (
    <div className="flex items-center gap-1.5">
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: statusColor }}
      />
      <span
        className="truncate text-xs"
        style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
      >
        {lastTool.tool_name}
      </span>
      <span
        className="text-[10px]"
        style={{ color: 'var(--outline)' }}
      >
        ({tools.length})
      </span>
    </div>
  )
}
