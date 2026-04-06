import { useState } from 'react'

interface TimelineScrubberProps {
  totalDuration: number
  currentTime: number
  playing: boolean
  onSeek: (time: number) => void
  onTogglePlay: () => void
}

export function TimelineScrubber({
  totalDuration,
  currentTime,
  playing,
  onSeek,
  onTogglePlay,
}: TimelineScrubberProps) {
  const [hovering, setHovering] = useState(false)
  const progress = totalDuration > 0 ? (currentTime / totalDuration) * 100 : 0

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m}:${String(s).padStart(2, '0')}`
  }

  return (
    <div
      className="flex items-center gap-3 rounded-lg px-4 py-2"
      style={{ background: 'var(--surface-container)' }}
    >
      <button
        onClick={onTogglePlay}
        className="flex h-8 w-8 items-center justify-center rounded-full transition-colors"
        style={{ background: 'var(--primary-container)', color: 'var(--on-primary)' }}
      >
        {playing ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="4" width="4" height="16" />
            <rect x="14" y="4" width="4" height="16" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5,3 19,12 5,21" />
          </svg>
        )}
      </button>

      <span
        className="w-12 text-right text-xs tabular-nums"
        style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
      >
        {formatTime(currentTime)}
      </span>

      <div
        className="relative flex-1 cursor-pointer"
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const pct = (e.clientX - rect.left) / rect.width
          onSeek(pct * totalDuration)
        }}
      >
        <div
          className="h-1.5 rounded-full"
          style={{ background: 'var(--surface-container-highest)' }}
        >
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${progress}%`, background: 'var(--primary)' }}
          />
        </div>
        {hovering && (
          <div
            className="absolute top-0 h-1.5 w-2 -translate-x-1/2 rounded-full"
            style={{
              left: `${progress}%`,
              background: 'var(--on-surface)',
            }}
          />
        )}
      </div>

      <span
        className="w-12 text-xs tabular-nums"
        style={{ color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}
      >
        {formatTime(totalDuration)}
      </span>
    </div>
  )
}
