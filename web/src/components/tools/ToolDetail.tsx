import { motion } from 'framer-motion'
import type { ToolCall } from '../../types/events'

interface ToolDetailProps {
  tool: ToolCall
  onClose: () => void
}

export function ToolDetail({ tool, onClose }: ToolDetailProps) {
  const statusColor =
    tool.status === 'success' ? 'var(--tertiary)' :
    tool.status === 'error' ? 'var(--error)' :
    'var(--primary)'

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="overflow-hidden rounded-lg"
      style={{
        background: 'var(--surface-container)',
        border: '1px solid var(--outline-variant)',
      }}
    >
      <div className="flex items-center justify-between border-b px-3 py-2" style={{ borderColor: 'var(--outline-variant)' }}>
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-semibold"
            style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-mono)' }}
          >
            {tool.tool_name}
          </span>
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase"
            style={{ background: `${statusColor}15`, color: statusColor }}
          >
            {tool.status}
          </span>
          {tool.duration_ms != null && (
            <span className="text-[10px]" style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}>
              {tool.duration_ms}ms
            </span>
          )}
        </div>
        <button onClick={onClose} className="text-xs" style={{ color: 'var(--outline)' }}>
          Close
        </button>
      </div>

      {tool.arguments_preview && (
        <div className="border-b px-3 py-2" style={{ borderColor: 'var(--outline-variant)' }}>
          <span className="text-[10px] font-semibold uppercase" style={{ color: 'var(--outline)' }}>
            Input
          </span>
          <pre
            className="mt-1 max-h-32 overflow-auto text-[10px] leading-relaxed"
            style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
          >
            {tool.arguments_preview}
          </pre>
        </div>
      )}

      {tool.result_preview && (
        <div className="px-3 py-2">
          <span className="text-[10px] font-semibold uppercase" style={{ color: 'var(--outline)' }}>
            Output
          </span>
          <pre
            className="mt-1 max-h-32 overflow-auto text-[10px] leading-relaxed"
            style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
          >
            {tool.result_preview}
          </pre>
        </div>
      )}
    </motion.div>
  )
}
