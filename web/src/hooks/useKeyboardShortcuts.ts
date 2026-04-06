import { useEffect } from 'react'
import { useUIStore, type ActiveView } from '../stores/ui'
import { useTerminalStore } from '../stores/terminal'

const VIEW_KEYS: Record<string, ActiveView> = {
  w: 'warroom',
  b: 'board',
  p: 'pipeline',
  a: 'artifacts',
}

const STAGE_NAMES = [
  'requirements',
  'design',
  'implementation',
  'testing',
  'deployment',
  'monitoring',
]

export function useKeyboardShortcuts() {
  const setActiveView = useUIStore((s) => s.setActiveView)
  const selectAgent = useUIStore((s) => s.selectAgent)
  const toggleStage = useUIStore((s) => s.toggleStage)
  const toggleTerminal = useTerminalStore((s) => s.toggleCollapsed)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't capture when typing in inputs
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target instanceof HTMLElement && e.target.isContentEditable)
      ) {
        return
      }

      const key = e.key.toLowerCase()

      // View switching: W, B, P, A
      if (VIEW_KEYS[key] && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        setActiveView(VIEW_KEYS[key])
        return
      }

      // Toggle terminal: T
      if (key === 't' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        toggleTerminal()
        return
      }

      // Focus terminal: backtick
      if (key === '`' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        const terminal = document.querySelector('[data-terminal-output]')
        if (terminal instanceof HTMLElement) {
          terminal.focus()
        }
        return
      }

      // Escape: close panels/deselect
      if (key === 'escape') {
        selectAgent(null)
        return
      }

      // 1-6: Jump to stage
      const stageIndex = parseInt(key, 10) - 1
      if (stageIndex >= 0 && stageIndex < 6 && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        toggleStage(STAGE_NAMES[stageIndex])
        return
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [setActiveView, selectAgent, toggleStage, toggleTerminal])
}
