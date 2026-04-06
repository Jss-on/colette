import { create } from 'zustand'

interface TerminalTabState {
  agentId: string
  displayName: string
  stage: string
  chunks: string[]
  unread: number
}

interface TerminalStore {
  collapsed: boolean
  height: number
  activeTab: string | null
  tabs: Record<string, TerminalTabState>
  toggleCollapsed: () => void
  setHeight: (h: number) => void
  setActiveTab: (agentId: string) => void
  appendChunk: (agentId: string, chunk: string, stage: string, displayName: string) => void
  markRead: (agentId: string) => void
}

export const useTerminalStore = create<TerminalStore>((set, get) => ({
  collapsed: false,
  height: 30,
  activeTab: null,
  tabs: {},

  toggleCollapsed: () => set((s) => ({ collapsed: !s.collapsed })),

  setHeight: (h) => set({ height: Math.max(10, Math.min(70, h)) }),

  setActiveTab: (agentId) => {
    set({ activeTab: agentId })
    const tab = get().tabs[agentId]
    if (tab) {
      set((s) => ({
        tabs: { ...s.tabs, [agentId]: { ...tab, unread: 0 } },
      }))
    }
  },

  appendChunk: (agentId, chunk, stage, displayName) => {
    const state = get()
    const existing = state.tabs[agentId]
    const isActive = state.activeTab === agentId

    const updatedTab: TerminalTabState = existing
      ? {
          ...existing,
          chunks: [...existing.chunks, chunk],
          unread: isActive ? 0 : existing.unread + 1,
        }
      : {
          agentId,
          displayName,
          stage,
          chunks: [chunk],
          unread: isActive ? 0 : 1,
        }

    const updates: Partial<TerminalStore> = {
      tabs: { ...state.tabs, [agentId]: updatedTab },
    }

    // Auto-select first active tab
    if (!state.activeTab) {
      updates.activeTab = agentId
    }

    set(updates)
  },

  markRead: (agentId) => {
    const tab = get().tabs[agentId]
    if (tab) {
      set((s) => ({
        tabs: { ...s.tabs, [agentId]: { ...tab, unread: 0 } },
      }))
    }
  },
}))
