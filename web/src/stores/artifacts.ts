import { create } from 'zustand'

export interface ArtifactFile {
  id: string
  path: string
  stage: string
  agent: string
  language: string
  size_bytes: number
  content?: string
  content_preview?: string
  isNew: boolean
  timestamp: string
}

export interface ArtifactTab {
  fileId: string
  path: string
}

interface ArtifactStore {
  files: Record<string, ArtifactFile>
  openTabs: ArtifactTab[]
  activeTabId: string | null
  selectedFileId: string | null
  searchQuery: string
  addFile: (file: ArtifactFile) => void
  selectFile: (fileId: string) => void
  openTab: (fileId: string) => void
  closeTab: (fileId: string) => void
  setActiveTab: (fileId: string) => void
  setFileContent: (fileId: string, content: string) => void
  setSearchQuery: (query: string) => void
}

export const useArtifactStore = create<ArtifactStore>((set, get) => ({
  files: {},
  openTabs: [],
  activeTabId: null,
  selectedFileId: null,
  searchQuery: '',

  addFile: (file) =>
    set((s) => ({
      files: { ...s.files, [file.id]: file },
    })),

  selectFile: (fileId) => {
    set({ selectedFileId: fileId })
    // Also open a tab
    get().openTab(fileId)
  },

  openTab: (fileId) => {
    const state = get()
    const file = state.files[fileId]
    if (!file) return
    const exists = state.openTabs.some((t) => t.fileId === fileId)
    if (!exists) {
      set((s) => ({
        openTabs: [...s.openTabs, { fileId, path: file.path }],
        activeTabId: fileId,
      }))
    } else {
      set({ activeTabId: fileId })
    }
  },

  closeTab: (fileId) =>
    set((s) => {
      const tabs = s.openTabs.filter((t) => t.fileId !== fileId)
      return {
        openTabs: tabs,
        activeTabId: s.activeTabId === fileId ? (tabs[tabs.length - 1]?.fileId ?? null) : s.activeTabId,
      }
    }),

  setActiveTab: (fileId) => set({ activeTabId: fileId }),

  setFileContent: (fileId, content) =>
    set((s) => {
      const file = s.files[fileId]
      if (!file) return s
      return {
        files: { ...s.files, [fileId]: { ...file, content, isNew: false } },
      }
    }),

  setSearchQuery: (query) => set({ searchQuery: query }),
}))
