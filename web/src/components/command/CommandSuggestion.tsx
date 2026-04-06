import type { CommandItem } from '../../stores/command'

interface CommandSuggestionProps {
  command: CommandItem
  active: boolean
  onClick: () => void
}

export function CommandSuggestion({ command, active, onClick }: CommandSuggestionProps) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors"
      style={{
        background: active ? 'var(--surface-container-high)' : 'transparent',
      }}
    >
      <span
        className="shrink-0 text-xs font-semibold"
        style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)' }}
      >
        {command.label}
      </span>
      <span className="flex-1 truncate text-xs" style={{ color: 'var(--on-surface-variant)' }}>
        {command.description}
      </span>
      {command.shortcut && (
        <span
          className="shrink-0 rounded px-1.5 py-0.5 text-[10px]"
          style={{
            background: 'var(--surface-container-highest)',
            color: 'var(--outline)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {command.shortcut}
        </span>
      )}
    </button>
  )
}
