import { useParams } from 'react-router'
import { Layout } from '../components/shared/Layout'
import { useWebSocket } from '../hooks/useWebSocket'

export function ProjectDashboard() {
  const { id } = useParams<{ id: string }>()
  const ws = useWebSocket(id)

  return (
    <Layout>
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Project Dashboard
        </h1>
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs"
          style={{
            background: ws.connected ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)',
            color: ws.connected ? 'var(--green)' : 'var(--red)',
          }}
        >
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: ws.connected ? 'var(--green)' : 'var(--red)' }}
          />
          {ws.connected ? 'Connected' : ws.reconnecting ? 'Reconnecting...' : 'Disconnected'}
        </span>
      </div>
      <p style={{ color: 'var(--text-secondary)' }}>
        Board view coming in Phase 2.
      </p>
    </Layout>
  )
}
