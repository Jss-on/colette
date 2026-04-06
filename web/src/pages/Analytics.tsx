import { Layout } from '../components/shared/Layout'
import { TokenChart } from '../components/analytics/TokenChart'
import { CostEstimate } from '../components/analytics/CostEstimate'
import { AgentPerformance } from '../components/analytics/AgentPerformance'

// Placeholder data -- will be replaced with API calls when backend endpoints exist
const PLACEHOLDER_STAGES = [
  { stage: 'requirements', tokens: 2200 },
  { stage: 'design', tokens: 5400 },
  { stage: 'implementation', tokens: 22000 },
  { stage: 'testing', tokens: 8200 },
  { stage: 'deployment', tokens: 3100 },
  { stage: 'monitoring', tokens: 1947 },
]

const PLACEHOLDER_AGENTS = [
  { agent_id: 'researcher', display_name: 'Researcher', stage: 'requirements', tokens_used: 1200, duration_seconds: 32, tool_call_count: 3, tool_error_count: 0 },
  { agent_id: 'analyst', display_name: 'Analyst', stage: 'requirements', tokens_used: 1000, duration_seconds: 28, tool_call_count: 2, tool_error_count: 0 },
  { agent_id: 'architect', display_name: 'Architect', stage: 'design', tokens_used: 3200, duration_seconds: 45, tool_call_count: 5, tool_error_count: 0 },
  { agent_id: 'backend', display_name: 'Backend Dev', stage: 'implementation', tokens_used: 12000, duration_seconds: 180, tool_call_count: 24, tool_error_count: 1 },
  { agent_id: 'frontend', display_name: 'Frontend Dev', stage: 'implementation', tokens_used: 10000, duration_seconds: 160, tool_call_count: 18, tool_error_count: 0 },
]

export function Analytics() {
  const totalTokens = PLACEHOLDER_STAGES.reduce((sum, s) => sum + s.tokens, 0)

  return (
    <Layout>
      <div className="mb-6">
        <h1
          className="text-lg font-bold"
          style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
        >
          Analytics
        </h1>
        <p className="mt-1 text-xs" style={{ color: 'var(--outline)' }}>
          Cross-project cost, token, and performance metrics
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <TokenChart data={PLACEHOLDER_STAGES} />
        </div>
        <div>
          <CostEstimate totalTokens={totalTokens} />
        </div>
      </div>

      <div className="mt-4">
        <AgentPerformance agents={PLACEHOLDER_AGENTS} />
      </div>
    </Layout>
  )
}
