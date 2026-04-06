import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useCommandStore } from '../../stores/command'
import { CommandSuggestion } from './CommandSuggestion'

export function CommandBar() {
  const open = useCommandStore((s) => s.open)
  const input = useCommandStore((s) => s.input)
  const filteredCommands = useCommandStore((s) => s.filteredCommands)
  const setOpen = useCommandStore((s) => s.setOpen)
  const setInput = useCommandStore((s) => s.setInput)
  const executeCommand = useCommandStore((s) => s.executeCommand)
  const toggle = useCommandStore((s) => s.toggle)

  const inputRef = useRef<HTMLInputElement>(null)
  const [activeIndex, setActiveIndex] = useState(0)

  // Ctrl+K / Cmd+K to toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        toggle()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [toggle])

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      setActiveIndex(0)
    }
  }, [open])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setOpen(false)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, filteredCommands.length - 1))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      if (input.startsWith('/') && filteredCommands[activeIndex]) {
        executeCommand(filteredCommands[activeIndex])
      } else if (input.trim()) {
        // Plain text = feedback
        window.dispatchEvent(
          new CustomEvent('colette:command', {
            detail: { id: 'feedback-text', action: 'feedback', label: input },
          }),
        )
        setOpen(false)
      }
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-start justify-center pt-[20vh]"
        >
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <motion.div
            initial={{ y: -10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -10, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="relative z-10 w-full max-w-lg overflow-hidden rounded-xl shadow-2xl"
            style={{
              background: 'var(--surface-container)',
              border: '1px solid var(--outline-variant)',
            }}
          >
            {/* Input */}
            <div
              className="flex items-center gap-3 border-b px-4 py-3"
              style={{ borderColor: 'var(--outline-variant)' }}
            >
              <span style={{ color: 'var(--primary)' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 5l7 7-7 7" />
                </svg>
              </span>
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => { setInput(e.target.value); setActiveIndex(0) }}
                onKeyDown={handleKeyDown}
                placeholder="Type a command or message to agents..."
                className="flex-1 border-none bg-transparent text-sm outline-none"
                style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-body)' }}
              />
              <span
                className="rounded px-1.5 py-0.5 text-[10px]"
                style={{
                  background: 'var(--surface-container-highest)',
                  color: 'var(--outline)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                Esc
              </span>
            </div>

            {/* Suggestions */}
            {filteredCommands.length > 0 && (
              <div className="max-h-[240px] overflow-y-auto p-1">
                {filteredCommands.map((cmd, i) => (
                  <CommandSuggestion
                    key={cmd.id}
                    command={cmd}
                    active={i === activeIndex}
                    onClick={() => executeCommand(cmd)}
                  />
                ))}
              </div>
            )}

            {/* Hint */}
            <div
              className="border-t px-4 py-2 text-[10px]"
              style={{ borderColor: 'var(--outline-variant)', color: 'var(--outline)' }}
            >
              Type plain text to send feedback to the active stage. Use / for commands.
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
