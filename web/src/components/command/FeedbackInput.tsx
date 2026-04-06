import { useState, useRef, useEffect } from 'react'

interface FeedbackInputProps {
  open: boolean
  onSubmit: (message: string) => void
  onClose: () => void
}

export function FeedbackInput({ open, onSubmit, onClose }: FeedbackInputProps) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  if (!open) return null

  const handleSubmit = () => {
    if (value.trim()) {
      onSubmit(value.trim())
      setValue('')
      onClose()
    }
  }

  return (
    <div
      className="flex items-center gap-2 rounded-lg border px-3 py-2"
      style={{
        background: 'var(--surface-container)',
        borderColor: 'var(--primary)',
      }}
    >
      <span className="text-xs" style={{ color: 'var(--primary)' }}>Feedback:</span>
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleSubmit()
          if (e.key === 'Escape') onClose()
        }}
        placeholder="Send feedback to the active stage..."
        className="flex-1 border-none bg-transparent text-xs outline-none"
        style={{ color: 'var(--on-surface)' }}
      />
      <button
        onClick={handleSubmit}
        className="rounded px-2 py-1 text-[10px] font-medium"
        style={{ background: 'var(--primary-container)', color: 'var(--on-primary)' }}
      >
        Send
      </button>
    </div>
  )
}
