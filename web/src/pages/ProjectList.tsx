import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { Layout } from '../components/shared/Layout'
import { fetchProjects } from '../hooks/useApi'

interface ProjectSummary {
  id: string
  name: string
  description: string
  status: string
  created_at: string
}

export function ProjectList() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    fetchProjects()
      .then((data) => {
        setProjects(
          (data.projects ?? []).map((p) => ({
            id: (p.id as string) ?? '',
            name: (p.name as string) ?? 'Untitled',
            description: (p.description as string) ?? '',
            status: (p.status as string) ?? 'unknown',
            created_at: (p.created_at as string) ?? '',
          }))
        )
      })
      .catch(() => setProjects([]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <Layout>
      <h1
        className="mb-6 text-2xl font-semibold"
        style={{ color: 'var(--text-primary)' }}
      >
        Projects
      </h1>
      {loading ? (
        <p style={{ color: 'var(--text-secondary)' }}>Loading...</p>
      ) : projects.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>
          No projects found. Submit one with{' '}
          <code className="rounded px-1 text-sm" style={{ background: 'var(--bg-surface-2)' }}>
            colette submit
          </code>
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => navigate(`/projects/${p.id}`)}
              className="cursor-pointer rounded-lg border p-4 text-left transition-colors"
              style={{
                background: 'var(--bg-surface)',
                borderColor: 'var(--border)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-surface-2)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--bg-surface)'
              }}
            >
              <div className="mb-1 font-medium" style={{ color: 'var(--text-primary)' }}>
                {p.name}
              </div>
              <div className="mb-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                {p.description || 'No description'}
              </div>
              <span
                className="inline-block rounded-full px-2 py-0.5 text-xs font-medium"
                style={{
                  background: 'var(--bg-surface-2)',
                  color: p.status === 'running' ? 'var(--accent)' : 'var(--text-secondary)',
                }}
              >
                {p.status}
              </span>
            </button>
          ))}
        </div>
      )}
    </Layout>
  )
}
