import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router'
import { Layout } from '../components/shared/Layout'
import { TimelineScrubber } from '../components/history/TimelineScrubber'

interface ReplayEvent {
  event_type: string
  stage: string
  agent: string
  message: string
  timestamp: string
  elapsed_seconds: number
}

export function RunReplay() {
  const { id, runId } = useParams<{ id: string; runId: string }>()
  const navigate = useNavigate()
  const [events, setEvents] = useState<ReplayEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    if (!runId) return
    setLoading(true)
    fetch(`/api/v1/runs/${runId}/events?limit=1000`)
      .then((res) => res.json())
      .then((data) => {
        setEvents(data.data ?? [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [runId])

  const totalDuration = events.length > 0 ? events[events.length - 1].elapsed_seconds : 0
  const currentTime = events[currentIndex]?.elapsed_seconds ?? 0

  useEffect(() => {
    if (!playing || currentIndex >= events.length - 1) return
    const interval = setInterval(() => {
      setCurrentIndex((i) => {
        if (i >= events.length - 1) {
          setPlaying(false)
          return i
        }
        return i + 1
      })
    }, 100)
    return () => clearInterval(interval)
  }, [playing, currentIndex, events.length])

  const handleSeek = useCallback(
    (time: number) => {
      const idx = events.findIndex((e) => e.elapsed_seconds >= time)
      setCurrentIndex(idx >= 0 ? idx : events.length - 1)
    },
    [events],
  )

  const visibleEvents = events.slice(0, currentIndex + 1)

  return (
    <Layout>
      <div className="mb-4 flex items-center gap-3">
        <button
          onClick={() => navigate(`/projects/${id}/history`)}
          className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/5"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
        </button>
        <h1
          className="text-lg font-bold"
          style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
        >
          Run Replay
        </h1>
        <span className="text-xs" style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}>
          {runId?.slice(0, 8)}
        </span>
      </div>

      {loading ? (
        <p className="py-8 text-center text-sm" style={{ color: 'var(--outline)' }}>
          Loading events...
        </p>
      ) : (
        <>
          <TimelineScrubber
            totalDuration={totalDuration}
            currentTime={currentTime}
            playing={playing}
            onSeek={handleSeek}
            onTogglePlay={() => setPlaying(!playing)}
          />

          <div className="mt-4 max-h-[60vh] space-y-1 overflow-y-auto">
            {visibleEvents.map((evt, i) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded-lg px-3 py-1.5 text-xs"
                style={{
                  background: i === currentIndex ? 'rgba(76, 215, 246, 0.04)' : 'transparent',
                }}
              >
                <span
                  className="w-14 shrink-0 text-right tabular-nums"
                  style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}
                >
                  {evt.elapsed_seconds.toFixed(1)}s
                </span>
                <span
                  className="w-28 shrink-0 truncate"
                  style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)' }}
                >
                  {evt.event_type}
                </span>
                <span className="shrink-0" style={{ color: 'var(--on-surface-variant)' }}>
                  {evt.agent || evt.stage}
                </span>
                <span className="flex-1 truncate" style={{ color: 'var(--outline)' }}>
                  {evt.message}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </Layout>
  )
}
