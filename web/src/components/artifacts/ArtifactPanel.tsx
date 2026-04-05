import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { fetchArtifacts, downloadArtifactZip } from '../../hooks/useApi'
import { FilePreview } from './FilePreview'
import { SearchBar } from '../shared/SearchBar'

interface Artifact {
  name: string
  stage: string
  type: string
  content?: string
}

export function ArtifactPanel() {
  const { id } = useParams<{ id: string }>()
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    fetchArtifacts(id)
      .then((data) => {
        setArtifacts(
          (data.artifacts ?? []).map((a) => ({
            name: (a.name as string) ?? '',
            stage: (a.stage as string) ?? '',
            type: (a.type as string) ?? '',
            content: a.content as string | undefined,
          }))
        )
      })
      .catch(() => setArtifacts([]))
      .finally(() => setLoading(false))
  }, [id])

  const filtered = artifacts.filter(
    (a) => !search || a.name.toLowerCase().includes(search.toLowerCase())
  )

  const byStage = filtered.reduce<Record<string, Artifact[]>>((acc, a) => {
    if (!acc[a.stage]) acc[a.stage] = []
    acc[a.stage].push(a)
    return acc
  }, {})

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <div className="w-64">
          <SearchBar onSearch={setSearch} placeholder="Search artifacts..." />
        </div>
      </div>

      {loading ? (
        <p style={{ color: 'var(--text-secondary)' }}>Loading artifacts...</p>
      ) : Object.keys(byStage).length === 0 ? (
        <div
          className="rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            No artifacts generated yet
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {Object.entries(byStage).map(([stage, files]) => (
            <div
              key={stage}
              className="rounded-lg border overflow-hidden"
              style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
            >
              <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderBottomColor: 'var(--border)' }}>
                <span className="text-sm font-semibold capitalize" style={{ color: 'var(--text-primary)' }}>
                  {stage}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {files.length} file{files.length !== 1 ? 's' : ''}
                  </span>
                  {id && (
                    <button
                      onClick={() => downloadArtifactZip(id, stage)}
                      className="rounded px-2 py-0.5 text-xs font-medium transition-colors"
                      style={{ background: 'var(--bg-surface-2)', color: 'var(--text-secondary)' }}
                    >
                      Download ZIP
                    </button>
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-1 p-2">
                {files.map((f) => (
                  <FilePreview key={f.name} name={f.name} content={f.content} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
