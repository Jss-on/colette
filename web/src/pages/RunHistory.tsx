import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { Layout } from '../components/shared/Layout'
import { RunCard } from '../components/history/RunCard'

interface RunSummary {
  id: string
  status: string
  current_stage: string
  total_tokens: number
  started_at: string
  completed_at: string | null
  duration_seconds: number
}

export function RunHistory() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    fetch(`/api/v1/projects/${id}/runs`)
      .then((res) => res.json())
      .then((data) => {
        setRuns(data.data ?? [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [id])

  return (
    <Layout>
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(`/projects/${id}`)}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/5"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <h1
            className="text-lg font-bold"
            style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
          >
            Run History
          </h1>
        </div>
      </div>

      {loading ? (
        <p className="py-8 text-center text-sm" style={{ color: 'var(--outline)' }}>
          Loading runs...
        </p>
      ) : runs.length === 0 ? (
        <p className="py-8 text-center text-sm" style={{ color: 'var(--outline)' }}>
          No pipeline runs found for this project.
        </p>
      ) : (
        <div className="space-y-3">
          {runs.map((run) => (
            <RunCard
              key={run.id}
              run={run}
              onClick={() => navigate(`/projects/${id}/runs/${run.id}`)}
            />
          ))}
        </div>
      )}
    </Layout>
  )
}
