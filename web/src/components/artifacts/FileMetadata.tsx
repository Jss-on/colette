import type { ArtifactFile } from '../../stores/artifacts'

interface FileMetadataProps {
  file: ArtifactFile | null
}

export function FileMetadata({ file }: FileMetadataProps) {
  if (!file) {
    return (
      <div className="p-4 text-center text-xs" style={{ color: 'var(--outline)' }}>
        No file selected
      </div>
    )
  }

  const rows: { label: string; value: string }[] = [
    { label: 'Path', value: file.path },
    { label: 'Stage', value: file.stage },
    { label: 'Agent', value: file.agent || 'Unknown' },
    { label: 'Language', value: file.language || 'text' },
    { label: 'Size', value: formatBytes(file.size_bytes) },
    { label: 'Created', value: new Date(file.timestamp).toLocaleTimeString() },
  ]

  return (
    <div className="space-y-3 p-3">
      <h4
        className="text-xs font-bold uppercase tracking-wider"
        style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
      >
        File Details
      </h4>

      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.label}>
            <span
              className="block text-[10px] uppercase tracking-wider"
              style={{ color: 'var(--outline)', fontFamily: 'var(--font-label)' }}
            >
              {row.label}
            </span>
            <span
              className="text-xs"
              style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>

      <button
        className="w-full rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
        style={{
          background: 'var(--surface-container-high)',
          color: 'var(--on-surface)',
          border: '1px solid var(--outline-variant)',
        }}
      >
        Download
      </button>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
