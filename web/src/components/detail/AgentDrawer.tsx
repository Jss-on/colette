import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { usePipelineStore } from '../../stores/pipeline'
import { useUIStore } from '../../stores/ui'
import { StatusCell } from '../board/StatusCell'
import { ModelCell } from '../board/ModelCell'
import { formatTokens, formatDuration } from '../../utils/format'
import { LiveOutput } from './LiveOutput'
import { ToolCallLog } from './ToolCallLog'
import { AgentConversation } from './AgentConversation'

type DrawerTab = 'output' | 'tools' | 'history'

export function AgentDrawer() {
  const selectedAgentId = useUIStore((s) => s.selectedAgentId)
  const selectAgent = useUIStore((s) => s.selectAgent)
  const agents = usePipelineStore((s) => s.agents)
  const [activeTab, setActiveTab] = useState<DrawerTab>('output')

  const agent = selectedAgentId ? agents[selectedAgentId] : null

  return (
    <AnimatePresence>
      {agent && (
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="fixed right-0 top-0 bottom-0 z-50 flex w-96 flex-col border-l"
          style={{ background: 'var(--bg-surface)', borderLeftColor: 'var(--border)' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderBottomColor: 'var(--border)' }}>
            <div className="flex items-center gap-2">
              <div
                className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold"
                style={{ background: 'var(--accent)', color: '#fff' }}
              >
                {agent.display_name.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  @{agent.display_name}
                </div>
                <div className="text-[10px] capitalize" style={{ color: 'var(--text-secondary)' }}>
                  {agent.stage}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusCell state={agent.state} />
              <button
                onClick={() => selectAgent(null)}
                className="rounded p-1 transition-colors"
                style={{ color: 'var(--text-secondary)' }}
                onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)' }}
                onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)' }}
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-4 border-b px-4 py-2" style={{ borderBottomColor: 'var(--border)' }}>
            <ModelCell model={agent.model} />
            <span className="text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>
              {formatTokens(agent.tokens_used)} tokens
            </span>
            <span className="text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>
              {formatDuration(agent.started_at ? Date.now() - new Date(agent.started_at).getTime() : 0)}
            </span>
          </div>

          {/* Tabs */}
          <div className="flex border-b" style={{ borderBottomColor: 'var(--border)' }}>
            {(['output', 'tools', 'history'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className="flex-1 px-3 py-2 text-xs font-medium capitalize transition-colors"
                style={{
                  color: activeTab === tab ? 'var(--accent)' : 'var(--text-secondary)',
                  borderBottom: activeTab === tab ? '2px solid var(--accent)' : '2px solid transparent',
                }}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {activeTab === 'output' && <LiveOutput agentId={agent.agent_id} />}
            {activeTab === 'tools' && <ToolCallLog agentId={agent.agent_id} />}
            {activeTab === 'history' && <AgentConversation agentId={agent.agent_id} />}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
