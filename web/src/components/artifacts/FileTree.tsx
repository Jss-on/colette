import { useMemo, useState } from 'react'
import type { ArtifactFile } from '../../stores/artifacts'

interface FileTreeProps {
  files: ArtifactFile[]
  selectedId: string | null
  searchQuery: string
  onSelect: (fileId: string) => void
}

interface StageGroup {
  stage: string
  files: ArtifactFile[]
}

export function FileTree({ files, selectedId, searchQuery, onSelect }: FileTreeProps) {
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set())

  const groups = useMemo(() => {
    const filtered = searchQuery
      ? files.filter((f) => f.path.toLowerCase().includes(searchQuery.toLowerCase()))
      : files

    const map = new Map<string, ArtifactFile[]>()
    for (const f of filtered) {
      const existing = map.get(f.stage) ?? []
      existing.push(f)
      map.set(f.stage, existing)
    }

    return Array.from(map.entries()).map(([stage, files]): StageGroup => ({ stage, files }))
  }, [files, searchQuery])

  const toggleStage = (stage: string) => {
    setExpandedStages((prev) => {
      const next = new Set(prev)
      if (next.has(stage)) {
        next.delete(stage)
      } else {
        next.add(stage)
      }
      return next
    })
  }

  return (
    <div className="space-y-0.5">
      {groups.map((group) => {
        const expanded = expandedStages.has(group.stage) || groups.length === 1
        return (
          <div key={group.stage}>
            <button
              onClick={() => toggleStage(group.stage)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs font-medium transition-colors hover:bg-white/5"
              style={{ color: 'var(--on-surface-variant)' }}
            >
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className={`transition-transform ${expanded ? 'rotate-90' : ''}`}
              >
                <path d="M9 18l6-6-6-6" />
              </svg>
              <span className="capitalize">{group.stage}</span>
              <span className="text-[10px]" style={{ color: 'var(--outline)' }}>
                ({group.files.length})
              </span>
            </button>
            {expanded && (
              <div className="ml-4 space-y-0.5">
                {group.files.map((file) => {
                  const fileName = file.path.split('/').pop() ?? file.path
                  return (
                    <button
                      key={file.id}
                      onClick={() => onSelect(file.id)}
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors"
                      style={{
                        color: selectedId === file.id ? 'var(--on-surface)' : 'var(--on-surface-variant)',
                        background: selectedId === file.id ? 'rgba(76, 215, 246, 0.06)' : 'transparent',
                      }}
                    >
                      {file.isNew && (
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full animate-pulse-cyan"
                          style={{ background: 'var(--primary)' }}
                        />
                      )}
                      <span className="truncate" style={{ fontFamily: 'var(--font-mono)' }}>
                        {fileName}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
      {groups.length === 0 && (
        <p className="py-4 text-center text-xs" style={{ color: 'var(--outline)' }}>
          {searchQuery ? 'No files match your search' : 'No artifacts generated yet'}
        </p>
      )}
    </div>
  )
}
