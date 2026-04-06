interface AgentMetric {
  agent_id: string
  display_name: string
  stage: string
  tokens_used: number
  duration_seconds: number
  tool_call_count: number
  tool_error_count: number
}

interface AgentPerformanceProps {
  agents: AgentMetric[]
}

export function AgentPerformance({ agents }: AgentPerformanceProps) {
  return (
    <div
      className="rounded-xl p-4"
      style={{ background: 'var(--surface-container-low)', border: '1px solid var(--outline-variant)' }}
    >
      <h3
        className="mb-3 text-xs font-bold uppercase tracking-wider"
        style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
      >
        Agent Performance
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr style={{ color: 'var(--outline)' }}>
              <th className="py-1.5 text-left font-medium">Agent</th>
              <th className="py-1.5 text-left font-medium">Stage</th>
              <th className="py-1.5 text-right font-medium">Tokens</th>
              <th className="py-1.5 text-right font-medium">Duration</th>
              <th className="py-1.5 text-right font-medium">Tools</th>
              <th className="py-1.5 text-right font-medium">Errors</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <tr
                key={agent.agent_id}
                className="border-t"
                style={{ borderColor: 'var(--outline-variant)' }}
              >
                <td className="py-1.5" style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-mono)' }}>
                  @{agent.display_name}
                </td>
                <td className="py-1.5 capitalize" style={{ color: 'var(--on-surface-variant)' }}>
                  {agent.stage}
                </td>
                <td
                  className="py-1.5 text-right tabular-nums"
                  style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
                >
                  {agent.tokens_used.toLocaleString()}
                </td>
                <td
                  className="py-1.5 text-right tabular-nums"
                  style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
                >
                  {agent.duration_seconds.toFixed(1)}s
                </td>
                <td
                  className="py-1.5 text-right tabular-nums"
                  style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}
                >
                  {agent.tool_call_count}
                </td>
                <td
                  className="py-1.5 text-right tabular-nums"
                  style={{
                    color: agent.tool_error_count > 0 ? 'var(--error)' : 'var(--on-surface-variant)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {agent.tool_error_count}
                </td>
              </tr>
            ))}
            {agents.length === 0 && (
              <tr>
                <td colSpan={6} className="py-4 text-center" style={{ color: 'var(--outline)' }}>
                  No agent data available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
