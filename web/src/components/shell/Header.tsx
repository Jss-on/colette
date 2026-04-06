interface HeaderProps {
  onToggleSidebar: () => void
}

export function Header({ onToggleSidebar }: HeaderProps) {
  return (
    <header
      className="sticky top-0 z-50 flex h-12 items-center justify-between px-4"
      style={{
        background: 'var(--surface-container-low)',
        borderBottom: '1px solid var(--outline-variant)',
      }}
    >
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-white/5"
          aria-label="Toggle sidebar"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 12h18M3 6h18M3 18h18" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          <span
            className="text-base font-bold tracking-tight"
            style={{ color: 'var(--primary)', fontFamily: 'var(--font-headline)' }}
          >
            COLETTE
          </span>
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
            style={{
              background: 'rgba(76, 215, 246, 0.1)',
              color: 'var(--primary)',
              border: '1px solid rgba(76, 215, 246, 0.2)',
            }}
          >
            Mission Control
          </span>
        </div>
      </div>

      <nav className="hidden items-center gap-1 md:flex">
        {['Missions', 'Assets', 'Fleet', 'Intelligence'].map((item) => (
          <button
            key={item}
            className="rounded-md px-3 py-1.5 text-xs font-medium transition-colors hover:bg-white/5"
            style={{ color: 'var(--on-surface-variant)' }}
          >
            {item}
          </button>
        ))}
      </nav>

      <div className="flex items-center gap-2">
        <button
          className="relative flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-white/5"
          aria-label="Notifications"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
        </button>
        <div
          className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold"
          style={{ background: 'var(--primary-container)', color: 'var(--on-primary)' }}
        >
          U
        </div>
      </div>
    </header>
  )
}
