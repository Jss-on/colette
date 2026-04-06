import { create } from 'zustand'

export interface CommandItem {
  id: string
  label: string
  description: string
  shortcut?: string
  action: string
}

const COMMANDS: CommandItem[] = [
  { id: 'pause', label: '/pause', description: 'Pause the current stage', shortcut: 'Space', action: 'pause' },
  { id: 'pause-all', label: '/pause-all', description: 'Pause the entire pipeline', action: 'pause-all' },
  { id: 'cancel', label: '/cancel', description: 'Cancel the pipeline', action: 'cancel' },
  { id: 'restart', label: '/restart', description: 'Restart the current stage', action: 'restart' },
  { id: 'skip', label: '/skip', description: 'Skip the current stage', action: 'skip' },
  { id: 'feedback', label: '/feedback', description: 'Send feedback to the active stage', action: 'feedback' },
  { id: 'edit-handoff', label: '/edit-handoff', description: 'Edit the last handoff', action: 'edit-handoff' },
]

interface CommandStore {
  open: boolean
  input: string
  filteredCommands: CommandItem[]
  setOpen: (open: boolean) => void
  toggle: () => void
  setInput: (value: string) => void
  executeCommand: (command: CommandItem) => void
}

export const useCommandStore = create<CommandStore>((set, get) => ({
  open: false,
  input: '',
  filteredCommands: COMMANDS,

  setOpen: (open) => set({ open, input: '', filteredCommands: COMMANDS }),

  toggle: () => {
    const current = get().open
    set({ open: !current, input: '', filteredCommands: COMMANDS })
  },

  setInput: (value) => {
    const lower = value.toLowerCase()
    const filtered = value.startsWith('/')
      ? COMMANDS.filter((c) => c.label.includes(lower) || c.description.toLowerCase().includes(lower))
      : COMMANDS
    set({ input: value, filteredCommands: filtered })
  },

  executeCommand: (command) => {
    set({ open: false, input: '' })
    // Command execution is handled by the component that reads this
    // Dispatch a custom event so any listener can react
    window.dispatchEvent(new CustomEvent('colette:command', { detail: command }))
  },
}))
