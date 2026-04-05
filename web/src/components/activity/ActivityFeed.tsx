import { useEffect, useRef, useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { usePipelineStore } from '../../stores/pipeline'
import { useUIStore } from '../../stores/ui'
import { EventType } from '../../types/events'
import { ActivityEntry } from './ActivityEntry'
import { ActivityFilter } from './ActivityFilter'

const SKIP_EVENTS = new Set([EventType.AGENT_STREAM_CHUNK, 'heartbeat'])

export function ActivityFeed() {
  const events = usePipelineStore((s) => s.events)
  const activityFilter = useUIStore((s) => s.activityFilter)
  const [autoScroll, setAutoScroll] = useState(true)
  const containerRef = useRef<HTMLDivElement>(null)
  const prevCountRef = useRef(0)

  const filtered = useMemo(() => {
    return events.filter((e) => {
      const eventType = e.type ?? (e as unknown as Record<string, unknown>).event_type as string
      if (SKIP_EVENTS.has(eventType as EventType)) return false
      if (activityFilter.type) {
        if (activityFilter.type === 'gate') {
          if (eventType !== EventType.GATE_PASSED && eventType !== EventType.GATE_FAILED) return false
        } else if (eventType !== activityFilter.type) {
          return false
        }
      }
      if (activityFilter.stage && e.stage !== activityFilter.stage) return false
      if (activityFilter.agent && e.agent !== activityFilter.agent) return false
      return true
    })
  }, [events, activityFilter])

  const newCount = filtered.length - prevCountRef.current

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
    prevCountRef.current = filtered.length
  }, [filtered.length, autoScroll])

  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }

  return (
    <div>
      <ActivityFilter />
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="relative flex flex-col gap-2 overflow-y-auto rounded-lg border p-4"
        style={{
          background: 'var(--bg-surface)',
          borderColor: 'var(--border)',
          maxHeight: 'calc(100vh - 280px)',
        }}
      >
        {filtered.length === 0 ? (
          <div className="py-8 text-center text-xs" style={{ color: 'var(--text-secondary)' }}>
            No events yet
          </div>
        ) : (
          filtered.map((event, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <ActivityEntry event={event} />
            </motion.div>
          ))
        )}
      </div>
      {!autoScroll && newCount > 0 && (
        <button
          onClick={() => {
            setAutoScroll(true)
            if (containerRef.current) {
              containerRef.current.scrollTop = containerRef.current.scrollHeight
            }
          }}
          className="sticky bottom-4 left-1/2 -translate-x-1/2 rounded-full px-3 py-1 text-xs font-medium"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          {newCount} new update{newCount !== 1 ? 's' : ''}
        </button>
      )}
    </div>
  )
}
