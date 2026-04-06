import { useState } from 'react'
import type { ToolCall } from '../../types/events'

interface ToolBlockProps {
  tool: ToolCall
  onExpand?: () => void
}

export function ToolBlock({ tool, onExpand }: ToolBlockProps) {
  const [hovered, setHovered] = useState(false)

  const color =
    tool.status === 'success' ? 'var(--tertiary)' :
    tool.status === 'error' ? 'var(--error)' :
    tool.status === 'running' ? 'var(--primary)' :
    'var(--amber)'

  return (
    <div className="relative">
      <button
        onClick={onExpand}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[10px] transition-colors"
        style={{
          background: `${color}10`,
          border: `1px solid ${color}30`,
          color,
          fontFamily: 'var(--font-mono)',
        }}
      >
        <span className="font-semibold">{tool.tool_name}</span>
        {tool.duration_ms != null && (
          <span style={{ color: 'var(--on-surface-variant)' }}>
            {tool.duration_ms < 1000
              ? `${tool.duration_ms}ms`
              : `${(tool.duration_ms / 1000).toFixed(1)}s`}
          </span>
        )}
      </button>

      {/* Hover tooltip */}
      {hovered && tool.arguments_preview && (
        <div
          className="absolute bottom-full left-0 z-50 mb-1 max-w-xs rounded-lg p-2 text-[10px] shadow-lg"
          style={{
            background: 'var(--surface-container-high)',
            border: '1px solid var(--outline-variant)',
            color: 'var(--on-surface-variant)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          <pre className="whitespace-pre-wrap break-words">{tool.arguments_preview}</pre>
        </div>
      )}
    </div>
  )
}
