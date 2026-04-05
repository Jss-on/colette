import { useParams } from 'react-router'
import { Layout } from '../components/shared/Layout'
import { MetricsBar } from '../components/shared/MetricsBar'
import { ViewSwitcher } from '../components/shared/ViewSwitcher'
import { AgentBoard } from '../components/board/AgentBoard'
import { PipelineView } from '../components/pipeline/PipelineView'
import { useWebSocket } from '../hooks/useWebSocket'
import { useUIStore } from '../stores/ui'

export function ProjectDashboard() {
  const { id } = useParams<{ id: string }>()
  const ws = useWebSocket(id)
  const activeView = useUIStore((s) => s.activeView)

  return (
    <Layout>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
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
            {ws.connected ? 'Live' : ws.reconnecting ? 'Reconnecting...' : 'Disconnected'}
          </span>
        </div>
        <ViewSwitcher />
      </div>

      <MetricsBar />

      {activeView === 'board' && <AgentBoard />}
      {activeView === 'pipeline' && <PipelineView />}
      {activeView === 'activity' && (
        <p style={{ color: 'var(--text-secondary)' }}>Activity feed coming in Phase 4.</p>
      )}
      {activeView === 'artifacts' && (
        <p style={{ color: 'var(--text-secondary)' }}>Artifacts view coming in Phase 5.</p>
      )}
    </Layout>
  )
}
