import type { ReactNode } from 'react'
import { Shell } from '../shell/Shell'

interface LayoutProps {
  children: ReactNode
  showTerminal?: boolean
}

export function Layout({ children, showTerminal = false }: LayoutProps) {
  return <Shell showTerminal={showTerminal}>{children}</Shell>
}
