import type { ReactNode } from 'react'
import { Shell } from '../shell/Shell'

interface LayoutProps {
  children: ReactNode
  showTerminal?: boolean
  showDecisionRail?: boolean
}

export function Layout({ children, showTerminal = false, showDecisionRail = false }: LayoutProps) {
  return (
    <Shell showTerminal={showTerminal} showDecisionRail={showDecisionRail}>
      {children}
    </Shell>
  )
}
