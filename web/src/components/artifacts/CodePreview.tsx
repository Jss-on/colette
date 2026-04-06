import { useMemo } from 'react'
import type { ArtifactFile } from '../../stores/artifacts'
import { highlightCode, detectLanguage } from '../../utils/highlighter'

interface CodePreviewProps {
  file: ArtifactFile | null
}

export function CodePreview({ file }: CodePreviewProps) {
  const html = useMemo(() => {
    if (!file?.content) return null
    const lang = detectLanguage(file.path)
    return highlightCode(file.content, lang)
  }, [file])

  if (!file) {
    return (
      <div
        className="flex h-full items-center justify-center"
        style={{ background: 'var(--surface-dim)' }}
      >
        <p className="text-xs" style={{ color: 'var(--outline)' }}>
          Select a file to preview
        </p>
      </div>
    )
  }

  return (
    <div
      className="h-full overflow-auto p-4"
      style={{
        background: 'var(--surface-dim)',
        fontFamily: 'var(--font-mono)',
      }}
    >
      {html ? (
        <pre
          className="text-xs leading-relaxed"
          style={{ color: 'var(--on-surface)' }}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : file.content_preview ? (
        <pre
          className="text-xs leading-relaxed"
          style={{ color: 'var(--on-surface)' }}
        >
          {file.content_preview}
        </pre>
      ) : (
        <p className="text-xs" style={{ color: 'var(--outline)' }}>
          Loading content...
        </p>
      )}
    </div>
  )
}
