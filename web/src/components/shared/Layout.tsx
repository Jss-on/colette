import type { ReactNode } from 'react'

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      <header
        className="sticky top-0 z-50 flex items-center justify-between px-6 py-3"
        style={{
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div className="flex items-center gap-3">
          <span className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
            Colette
          </span>
          <span
            className="rounded px-2 py-0.5 text-xs font-medium"
            style={{ background: 'var(--bg-surface-2)', color: 'var(--text-secondary)' }}
          >
            Agent Board
          </span>
        </div>
      </header>
      <main className="p-6">{children}</main>
    </div>
  )
}
