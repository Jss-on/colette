import { create } from 'zustand'

export type DecisionType = 'gate_passed' | 'gate_failed' | 'approval_required' | 'handoff' | 'escalation' | 'operator'

export interface DecisionEntry {
  id: string
  type: DecisionType
  timestamp: string
  stage: string
  title: string
  detail: string
  score?: number
  threshold?: number
  reasons?: string[]
  approvalId?: string
  resolved: boolean
}

interface DecisionStore {
  entries: DecisionEntry[]
  railVisible: boolean
  notificationCount: number
  addEntry: (entry: DecisionEntry) => void
  resolveEntry: (id: string) => void
  toggleRail: () => void
  clearNotifications: () => void
}

export const useDecisionStore = create<DecisionStore>((set) => ({
  entries: [],
  railVisible: true,
  notificationCount: 0,

  addEntry: (entry) =>
    set((s) => ({
      entries: [entry, ...s.entries],
      notificationCount: entry.type === 'approval_required' ? s.notificationCount + 1 : s.notificationCount,
    })),

  resolveEntry: (id) =>
    set((s) => ({
      entries: s.entries.map((e) => (e.id === id ? { ...e, resolved: true } : e)),
    })),

  toggleRail: () => set((s) => ({ railVisible: !s.railVisible })),

  clearNotifications: () => set({ notificationCount: 0 }),
}))
