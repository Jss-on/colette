import { SearchBar } from '../shared/SearchBar'

interface BoardToolbarProps {
  onSearch: (query: string) => void
}

export function BoardToolbar({ onSearch }: BoardToolbarProps) {
  return (
    <div className="mb-4 flex items-center gap-4">
      <div className="w-64">
        <SearchBar onSearch={onSearch} placeholder="Filter agents..." />
      </div>
    </div>
  )
}
