import { useParams } from 'react-router'
import { Layout } from '../components/shared/Layout'
import { MetricsBar } from '../components/shared/MetricsBar'
import { ViewSwitcher } from '../components/shared/ViewSwitcher'
import { WarRoom } from '../components/warroom/WarRoom'
import { AgentBoard } from '../components/board/AgentBoard'
import { PipelineView } from '../components/pipeline/PipelineView'
import { AgentDrawer } from '../components/detail/AgentDrawer'
import { ActivityFeed } from '../components/activity/ActivityFeed'
import { ArtifactWorkshop } from '../components/artifacts/ArtifactWorkshop'
import { CommandBar } from '../components/command/CommandBar'
import { useWebSocket } from '../hooks/useWebSocket'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { useNotifications } from '../hooks/useNotifications'
import { useUIStore } from '../stores/ui'

export function ProjectDashboard() {
  const { id } = useParams<{ id: string }>()
  const ws = useWebSocket(id)
  const activeView = useUIStore((s) => s.activeView)

  useKeyboardShortcuts()
  useNotifications()

  return (
    <Layout showTerminal showDecisionRail>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <h1
            className="text-lg font-bold"
            style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
          >
            Project Dashboard
          </h1>
          <ConnectionBadge connected={ws.connected} reconnecting={ws.reconnecting} />
        </div>
        <ViewSwitcher />
      </div>

      <MetricsBar />

      {activeView === 'warroom' && <WarRoom />}
      {activeView === 'board' && <AgentBoard />}
      {activeView === 'pipeline' && <PipelineView />}
      {activeView === 'activity' && <ActivityFeed />}
      {activeView === 'artifacts' && <ArtifactWorkshop />}

      <AgentDrawer />
      <CommandBar />
    </Layout>
  )
}

function ConnectionBadge({ connected, reconnecting }: { connected: boolean; reconnecting: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium"
      style={{
        background: connected ? 'rgba(78, 222, 163, 0.1)' : 'rgba(255, 180, 171, 0.1)',
        color: connected ? 'var(--tertiary)' : 'var(--error)',
      }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: connected ? 'var(--tertiary)' : 'var(--error)' }}
      />
      {connected ? 'Live' : reconnecting ? 'Reconnecting...' : 'Disconnected'}
    </span>
  )
}
