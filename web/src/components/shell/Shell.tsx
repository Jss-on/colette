import { useState, type ReactNode } from 'react'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { StatusFooter } from './StatusFooter'
import { LiveTerminal } from '../terminal/LiveTerminal'
import { DecisionRail } from '../decisions/DecisionRail'

interface ShellProps {
  children: ReactNode
  showTerminal?: boolean
  showDecisionRail?: boolean
}

export function Shell({ children, showTerminal = false, showDecisionRail = false }: ShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--surface)' }}>
      <Header onToggleSidebar={() => setSidebarCollapsed((c) => !c)} />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar collapsed={sidebarCollapsed} />

        <div className="flex flex-1 overflow-hidden">
          <div className="flex flex-1 flex-col overflow-hidden">
            <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
            {showTerminal && <LiveTerminal />}
          </div>
          {showDecisionRail && <DecisionRail />}
        </div>
      </div>

      <StatusFooter />
    </div>
  )
}
