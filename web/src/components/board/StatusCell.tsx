import { motion } from 'framer-motion'
import type { AgentState } from '../../types/events'
import { statusColor } from '../../utils/colors'

interface StatusCellProps {
  state: AgentState
}

const STATE_LABELS: Record<AgentState, string> = {
  idle: 'Idle',
  thinking: 'Thinking',
  tool_use: 'Tool Use',
  reviewing: 'Reviewing',
  handing_off: 'Handing Off',
  done: 'Done',
  error: 'Error',
}

export function StatusCell({ state }: StatusCellProps) {
  const color = statusColor(state)

  return (
    <motion.span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{
        color,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
      }}
      animate={{ backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)` }}
      transition={{ duration: 0.4 }}
    >
      {(state === 'thinking' || state === 'tool_use') && (
        <motion.span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ background: color }}
          animate={
            state === 'thinking'
              ? { opacity: [1, 0.4, 1] }
              : { rotate: 360 }
          }
          transition={{ duration: 1, repeat: Infinity }}
        />
      )}
      {state === 'done' && (
        <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      )}
      {STATE_LABELS[state]}
    </motion.span>
  )
}
