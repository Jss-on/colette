import { create } from 'zustand'

export type ActiveView = 'warroom' | 'board' | 'pipeline' | 'activity' | 'artifacts'

interface UIStore {
  activeView: ActiveView
  selectedAgentId: string | null
  expandedStages: Set<string>
  activityFilter: { stage?: string; agent?: string; type?: string }
  sidebarCollapsed: boolean
  setActiveView: (view: ActiveView) => void
  selectAgent: (id: string | null) => void
  toggleStage: (stage: string) => void
  setActivityFilter: (filter: { stage?: string; agent?: string; type?: string }) => void
  toggleSidebar: () => void
}

export const useUIStore = create<UIStore>((set) => ({
  activeView: 'board',
  selectedAgentId: null,
  expandedStages: new Set<string>(),
  activityFilter: {},
  sidebarCollapsed: false,

  setActiveView: (view) => set({ activeView: view }),

  selectAgent: (id) => set({ selectedAgentId: id }),

  toggleStage: (stage) =>
    set((state) => {
      const next = new Set(state.expandedStages)
      if (next.has(stage)) {
        next.delete(stage)
      } else {
        next.add(stage)
      }
      return { expandedStages: next }
    }),

  setActivityFilter: (filter) => set({ activityFilter: filter }),

  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}))
