import { create } from 'zustand'

export type ActiveView = 'board' | 'pipeline' | 'activity' | 'artifacts'

interface UIStore {
  activeView: ActiveView
  selectedAgentId: string | null
  expandedStages: Set<string>
  activityFilter: { stage?: string; agent?: string; type?: string }
  setActiveView: (view: ActiveView) => void
  selectAgent: (id: string | null) => void
  toggleStage: (stage: string) => void
  setActivityFilter: (filter: { stage?: string; agent?: string; type?: string }) => void
}

export const useUIStore = create<UIStore>((set) => ({
  activeView: 'board',
  selectedAgentId: null,
  expandedStages: new Set<string>(),
  activityFilter: {},

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
}))
