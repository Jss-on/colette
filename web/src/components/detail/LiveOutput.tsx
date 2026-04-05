import { useEffect, useRef } from 'react'
import { usePipelineStore } from '../../stores/pipeline'
import { EventType } from '../../types/events'

interface LiveOutputProps {
  agentId: string
}

export function LiveOutput({ agentId }: LiveOutputProps) {
  const events = usePipelineStore((s) => s.events)
  const containerRef = useRef<HTMLDivElement>(null)

  const chunks = events
    .filter(
      (e) =>
        e.agent === agentId &&
        (e.type === EventType.AGENT_STREAM_CHUNK ||
          (e as unknown as Record<string, unknown>).event_type === EventType.AGENT_STREAM_CHUNK)
    )
    .map((e) => e.message ?? '')

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [chunks.length])

  return (
    <div
      ref={containerRef}
      className="h-64 overflow-y-auto rounded-md p-3 font-mono text-xs leading-relaxed"
      style={{ background: '#0d1117', color: 'var(--text-primary)' }}
    >
      {chunks.length > 0 ? (
        chunks.map((chunk, i) => <span key={i}>{chunk}</span>)
      ) : (
        <span style={{ color: 'var(--text-secondary)' }}>Waiting for output...</span>
      )}
    </div>
  )
}
