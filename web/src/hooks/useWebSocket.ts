import { useCallback, useEffect, useRef, useState } from 'react'
import { usePipelineStore } from '../stores/pipeline'
import type { PipelineEvent } from '../types/events'

interface WebSocketState {
  connected: boolean
  reconnecting: boolean
  error: string | null
}

const INITIAL_RETRY_MS = 1000
const MAX_RETRY_MS = 30_000
const BATCH_INTERVAL_MS = 100

export function useWebSocket(projectId: string | undefined): WebSocketState {
  const [state, setState] = useState<WebSocketState>({
    connected: false,
    reconnecting: false,
    error: null,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(INITIAL_RETRY_MS)
  const batchRef = useRef<PipelineEvent[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mountedRef = useRef(true)

  const handleEvent = usePipelineStore((s) => s.handleEvent)
  const setInitialState = usePipelineStore((s) => s.setInitialState)

  const flushBatch = useCallback(() => {
    if (batchRef.current.length === 0) return
    const batch = batchRef.current
    batchRef.current = []
    for (const event of batch) {
      handleEvent(event)
    }
  }, [handleEvent])

  useEffect(() => {
    mountedRef.current = true
    if (!projectId) return

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const ws = new WebSocket(`${protocol}//${host}/projects/${projectId}/ws`)
      wsRef.current = ws

      ws.onopen = async () => {
        if (!mountedRef.current) return
        retryRef.current = INITIAL_RETRY_MS
        setState({ connected: true, reconnecting: false, error: null })

        try {
          const [agentsRes, convRes] = await Promise.all([
            fetch(`/api/v1/projects/${projectId}/agents`),
            fetch(`/api/v1/projects/${projectId}/conversation`),
          ])
          if (agentsRes.ok && convRes.ok) {
            const agents = await agentsRes.json()
            const conv = await convRes.json()
            setInitialState(agents.agents ?? [], conv.entries ?? [])
          }
        } catch {
          // Initial state fetch failed — will catch up via events
        }
      }

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as PipelineEvent
          if ((data as unknown as Record<string, unknown>).event_type === 'heartbeat') return
          batchRef.current.push(data)
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setState((s) => ({ ...s, connected: false, reconnecting: true }))
        const delay = retryRef.current
        retryRef.current = Math.min(delay * 2, MAX_RETRY_MS)
        setTimeout(connect, delay)
      }

      ws.onerror = () => {
        if (!mountedRef.current) return
        setState((s) => ({ ...s, error: 'WebSocket error' }))
        ws.close()
      }
    }

    connect()

    timerRef.current = setInterval(flushBatch, BATCH_INTERVAL_MS)

    return () => {
      mountedRef.current = false
      if (timerRef.current) clearInterval(timerRef.current)
      wsRef.current?.close()
    }
  }, [projectId, flushBatch, setInitialState])

  return state
}
