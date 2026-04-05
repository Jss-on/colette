import { useEffect } from 'react'
import { useParams } from 'react-router'
import { Layout } from '../components/shared/Layout'
import { MetricsBar } from '../components/shared/MetricsBar'
import { ViewSwitcher } from '../components/shared/ViewSwitcher'
import { AgentBoard } from '../components/board/AgentBoard'
import { PipelineView } from '../components/pipeline/PipelineView'
import { AgentDrawer } from '../components/detail/AgentDrawer'
import { ActivityFeed } from '../components/activity/ActivityFeed'
import { ArtifactPanel } from '../components/artifacts/ArtifactPanel'
import { ApprovalQueue } from '../components/approvals/ApprovalQueue'
import { useWebSocket } from '../hooks/useWebSocket'
import { useUIStore, type ActiveView } from '../stores/ui'

const VIEW_KEYS: Record<string, ActiveView> = {
  b: 'board',
  p: 'pipeline',
  a: 'activity',
  f: 'artifacts',
}

export function ProjectDashboard() {
  const { id } = useParams<{ id: string }>()
  const ws = useWebSocket(id)
  const activeView = useUIStore((s) => s.activeView)
  const setActiveView = useUIStore((s) => s.setActiveView)
  const selectAgent = useUIStore((s) => s.selectAgent)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      const key = e.key.toLowerCase()
      if (VIEW_KEYS[key]) {
        setActiveView(VIEW_KEYS[key])
        return
      }
      if (key === 'escape') {
        selectAgent(null)
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [setActiveView, selectAgent])

  return (
    <Layout>
      <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
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
      {activeView === 'activity' && <ActivityFeed />}
      {activeView === 'artifacts' && (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <ArtifactPanel />
          </div>
          <div>
            <ApprovalQueue />
          </div>
        </div>
      )}

      <AgentDrawer />
    </Layout>
  )
}
