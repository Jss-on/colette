import { useMemo } from 'react'
import { useArtifactStore } from '../../stores/artifacts'
import { FileTree } from './FileTree'
import { CodePreview } from './CodePreview'
import { FileMetadata } from './FileMetadata'

export function ArtifactWorkshop() {
  const files = useArtifactStore((s) => s.files)
  const selectedFileId = useArtifactStore((s) => s.selectedFileId)
  const openTabs = useArtifactStore((s) => s.openTabs)
  const activeTabId = useArtifactStore((s) => s.activeTabId)
  const searchQuery = useArtifactStore((s) => s.searchQuery)
  const selectFile = useArtifactStore((s) => s.selectFile)
  const setActiveTab = useArtifactStore((s) => s.setActiveTab)
  const closeTab = useArtifactStore((s) => s.closeTab)
  const setSearchQuery = useArtifactStore((s) => s.setSearchQuery)

  const fileList = useMemo(() => Object.values(files), [files])
  const activeFile = activeTabId ? files[activeTabId] ?? null : null

  return (
    <div
      className="grid gap-0 overflow-hidden rounded-xl"
      style={{
        gridTemplateColumns: '220px 1fr 200px',
        height: 'calc(100vh - 240px)',
        background: 'var(--surface-container-low)',
        border: '1px solid var(--outline-variant)',
      }}
    >
      {/* File Tree Panel */}
      <div
        className="flex flex-col overflow-hidden border-r"
        style={{ borderColor: 'var(--outline-variant)' }}
      >
        <div className="border-b p-2" style={{ borderColor: 'var(--outline-variant)' }}>
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search files..."
            className="w-full rounded-md border bg-transparent px-2 py-1 text-xs outline-none"
            style={{
              borderColor: 'var(--outline-variant)',
              color: 'var(--on-surface)',
            }}
          />
        </div>
        <div className="flex-1 overflow-y-auto p-1">
          <FileTree
            files={fileList}
            selectedId={selectedFileId}
            searchQuery={searchQuery}
            onSelect={selectFile}
          />
        </div>
      </div>

      {/* Code Preview Panel */}
      <div className="flex flex-col overflow-hidden">
        {/* Tabs */}
        {openTabs.length > 0 && (
          <div
            className="flex gap-0 border-b overflow-x-auto"
            style={{ borderColor: 'var(--outline-variant)' }}
          >
            {openTabs.map((tab) => (
              <div
                key={tab.fileId}
                className="flex items-center gap-1 border-b-2 px-3 py-1.5 text-xs cursor-pointer"
                style={{
                  borderColor: tab.fileId === activeTabId ? 'var(--primary)' : 'transparent',
                  color: tab.fileId === activeTabId ? 'var(--on-surface)' : 'var(--on-surface-variant)',
                  background: tab.fileId === activeTabId ? 'rgba(76, 215, 246, 0.04)' : 'transparent',
                  fontFamily: 'var(--font-mono)',
                }}
                onClick={() => setActiveTab(tab.fileId)}
              >
                <span className="truncate max-w-[120px]">
                  {tab.path.split('/').pop()}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); closeTab(tab.fileId) }}
                  className="ml-1 opacity-60 hover:opacity-100"
                >
                  x
                </button>
              </div>
            ))}
          </div>
        )}
        {/* Preview area */}
        <div className="flex-1 overflow-hidden">
          <CodePreview file={activeFile} />
        </div>
      </div>

      {/* Metadata Panel */}
      <div
        className="overflow-y-auto border-l"
        style={{ borderColor: 'var(--outline-variant)' }}
      >
        <FileMetadata file={activeFile} />
      </div>
    </div>
  )
}
