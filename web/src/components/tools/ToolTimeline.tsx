import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import type { ToolCall } from '../../types/events'
import { ToolBlock } from './ToolBlock'
import { ToolDetail } from './ToolDetail'

interface ToolTimelineProps {
  tools: ToolCall[]
}

export function ToolTimeline({ tools }: ToolTimelineProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)

  if (tools.length === 0) {
    return (
      <div className="py-2 text-center text-[10px]" style={{ color: 'var(--outline)' }}>
        No tool calls yet
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {/* Horizontal timeline strip */}
      <div className="flex flex-wrap items-center gap-1">
        {tools.map((tool, i) => (
          <div key={`${tool.tool_call_id ?? i}`} className="flex items-center gap-1">
            <ToolBlock
              tool={tool}
              onExpand={() => setExpandedIndex(expandedIndex === i ? null : i)}
            />
            {i < tools.length - 1 && (
              <div
                className="h-px w-3"
                style={{ background: 'var(--outline-variant)' }}
              />
            )}
          </div>
        ))}
      </div>

      {/* Expanded detail */}
      <AnimatePresence>
        {expandedIndex != null && tools[expandedIndex] && (
          <ToolDetail
            key={expandedIndex}
            tool={tools[expandedIndex]}
            onClose={() => setExpandedIndex(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
