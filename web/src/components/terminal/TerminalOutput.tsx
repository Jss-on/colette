import { useEffect, useRef, useState } from 'react'

interface TerminalOutputProps {
  chunks: string[]
}

export function TerminalOutput({ chunks }: TerminalOutputProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [showJump, setShowJump] = useState(false)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [chunks, autoScroll])

  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    const atBottom = scrollHeight - scrollTop - clientHeight < 40
    setAutoScroll(atBottom)
    setShowJump(!atBottom && chunks.length > 0)
  }

  const jumpToLatest = () => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
      setAutoScroll(true)
      setShowJump(false)
    }
  }

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={containerRef}
        data-terminal-output
        tabIndex={0}
        onScroll={handleScroll}
        className="h-full overflow-y-auto p-3 text-xs leading-relaxed outline-none"
        style={{
          background: 'var(--surface-dim)',
          color: 'var(--on-surface)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        {chunks.length === 0 ? (
          <span style={{ color: 'var(--outline)' }}>Waiting for agent output...</span>
        ) : (
          <pre className="whitespace-pre-wrap break-words">
            {chunks.join('')}
            <span className="stream-cursor" />
          </pre>
        )}
      </div>

      {showJump && (
        <button
          onClick={jumpToLatest}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full px-3 py-1 text-xs font-medium shadow-lg transition-colors"
          style={{
            background: 'var(--primary-container)',
            color: 'var(--on-primary)',
          }}
        >
          Jump to latest
        </button>
      )}
    </div>
  )
}
