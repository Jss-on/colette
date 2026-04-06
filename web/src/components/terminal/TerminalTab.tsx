interface TerminalTabProps {
  agentId: string
  displayName: string
  stage: string
  active: boolean
  unread: number
  onClick: () => void
}

export function TerminalTab({ displayName, stage, active, unread, onClick }: TerminalTabProps) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-1.5 text-xs font-medium transition-colors"
      style={{
        borderColor: active ? 'var(--primary)' : 'transparent',
        color: active ? 'var(--on-surface)' : 'var(--on-surface-variant)',
        background: active ? 'rgba(76, 215, 246, 0.06)' : 'transparent',
      }}
    >
      <span className="truncate max-w-[120px]">@{displayName}</span>
      {stage && (
        <span className="text-[10px]" style={{ color: 'var(--outline)' }}>
          {stage}
        </span>
      )}
      {unread > 0 && (
        <span
          className="flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-semibold"
          style={{ background: 'var(--primary-container)', color: 'var(--on-primary)' }}
        >
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </button>
  )
}
