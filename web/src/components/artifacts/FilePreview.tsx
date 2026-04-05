import { useState } from 'react'

interface FilePreviewProps {
  name: string
  content?: string
  language?: string
}

export function FilePreview({ name, content }: FilePreviewProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className="rounded-md border overflow-hidden"
      style={{ borderColor: 'var(--border)' }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors"
        style={{ background: 'var(--bg-surface-2)' }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg-surface-2)' }}
      >
        <svg className="h-3.5 w-3.5 flex-shrink-0" style={{ color: 'var(--text-secondary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span className="text-xs font-mono truncate" style={{ color: 'var(--text-primary)' }}>
          {name}
        </span>
        <svg
          className="ml-auto h-3 w-3 transition-transform"
          style={{
            color: 'var(--text-secondary)',
            transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
          }}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>
      {expanded && content && (
        <pre
          className="overflow-x-auto p-3 text-xs leading-relaxed"
          style={{ background: '#0d1117', color: 'var(--text-primary)' }}
        >
          <code>{content}</code>
        </pre>
      )}
    </div>
  )
}
