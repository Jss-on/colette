import { useCallback, useRef, useState } from 'react'
import { useTerminalStore } from '../../stores/terminal'
import { TerminalTab } from './TerminalTab'
import { TerminalOutput } from './TerminalOutput'

export function LiveTerminal() {
  const collapsed = useTerminalStore((s) => s.collapsed)
  const height = useTerminalStore((s) => s.height)
  const activeTab = useTerminalStore((s) => s.activeTab)
  const tabs = useTerminalStore((s) => s.tabs)
  const toggleCollapsed = useTerminalStore((s) => s.toggleCollapsed)
  const setHeight = useTerminalStore((s) => s.setHeight)
  const setActiveTab = useTerminalStore((s) => s.setActiveTab)

  const [dragging, setDragging] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const tabList = Object.values(tabs)
  const activeChunks = activeTab ? tabs[activeTab]?.chunks ?? [] : []

  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      setDragging(true)

      const startY = e.clientY
      const startHeight = height

      const onMove = (moveEvent: MouseEvent) => {
        const dy = startY - moveEvent.clientY
        const vh = (dy / window.innerHeight) * 100
        setHeight(startHeight + vh)
      }

      const onUp = () => {
        setDragging(false)
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onUp)
      }

      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
    },
    [height, setHeight],
  )

  if (collapsed) {
    return (
      <div
        className="flex h-8 items-center justify-between border-t px-3"
        style={{
          background: 'var(--surface-container-low)',
          borderColor: 'var(--outline-variant)',
        }}
      >
        <button
          onClick={toggleCollapsed}
          className="flex items-center gap-2 text-xs font-medium"
          style={{ color: 'var(--on-surface-variant)' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 15l-6-6-6 6" />
          </svg>
          Terminal
          {tabList.reduce((sum, t) => sum + t.unread, 0) > 0 && (
            <span
              className="flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-semibold"
              style={{ background: 'var(--primary-container)', color: 'var(--on-primary)' }}
            >
              {tabList.reduce((sum, t) => sum + t.unread, 0)}
            </span>
          )}
        </button>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="flex flex-col border-t"
      style={{
        height: `${height}vh`,
        borderColor: 'var(--outline-variant)',
        background: 'var(--surface-dim)',
      }}
    >
      {/* Drag handle */}
      <div
        onMouseDown={handleDragStart}
        className="flex h-1.5 cursor-row-resize items-center justify-center"
        style={{
          background: dragging ? 'var(--primary)' : 'var(--surface-container)',
        }}
      >
        <div
          className="h-0.5 w-8 rounded-full"
          style={{ background: 'var(--outline-variant)' }}
        />
      </div>

      {/* Tab bar */}
      <div
        className="flex items-center gap-0 border-b px-1"
        style={{
          background: 'var(--surface-container-low)',
          borderColor: 'var(--outline-variant)',
        }}
      >
        <div className="flex flex-1 items-center overflow-x-auto">
          {tabList.map((tab) => (
            <TerminalTab
              key={tab.agentId}
              agentId={tab.agentId}
              displayName={tab.displayName}
              stage={tab.stage}
              active={tab.agentId === activeTab}
              unread={tab.unread}
              onClick={() => setActiveTab(tab.agentId)}
            />
          ))}
          {tabList.length === 0 && (
            <span className="px-3 py-1.5 text-xs" style={{ color: 'var(--outline)' }}>
              No agent output yet
            </span>
          )}
        </div>
        <button
          onClick={toggleCollapsed}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded transition-colors hover:bg-white/5"
          aria-label="Collapse terminal"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
      </div>

      {/* Output area */}
      <TerminalOutput chunks={activeChunks} />
    </div>
  )
}
