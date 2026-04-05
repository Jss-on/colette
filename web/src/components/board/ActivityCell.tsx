import { useState } from 'react'

interface ActivityCellProps {
  activity: string
}

export function ActivityCell({ activity }: ActivityCellProps) {
  const [expanded, setExpanded] = useState(false)

  if (!activity) {
    return <span style={{ color: 'var(--text-secondary)' }}>—</span>
  }

  const truncated = activity.length > 80 && !expanded

  return (
    <span
      className="text-sm cursor-pointer"
      style={{ color: 'var(--text-secondary)' }}
      onClick={() => setExpanded(!expanded)}
      title={activity}
    >
      {truncated ? `${activity.slice(0, 80)}...` : activity}
    </span>
  )
}
