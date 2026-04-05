import type { StageInfo } from '../../types/events'
import { stageStatusColor } from '../../utils/colors'
import { formatDuration } from '../../utils/format'

interface GanttTimelineProps {
  stages: StageInfo[]
}

export function GanttTimeline({ stages }: GanttTimelineProps) {
  const maxElapsed = Math.max(...stages.map((s) => s.elapsed_ms), 1)

  return (
    <div
      className="rounded-lg border p-4"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
        Timeline
      </h3>
      <div className="flex flex-col gap-2">
        {stages.map((stage) => {
          const pct = (stage.elapsed_ms / maxElapsed) * 100
          const color = stageStatusColor(stage.status)

          return (
            <div key={stage.name} className="flex items-center gap-3">
              <span
                className="w-24 text-right text-xs capitalize truncate"
                style={{ color: 'var(--text-secondary)' }}
              >
                {stage.name}
              </span>
              <div
                className="flex-1 h-5 rounded overflow-hidden relative"
                style={{ background: 'var(--bg-surface-2)' }}
              >
                <div
                  className="h-full rounded transition-all duration-500"
                  style={{
                    width: `${Math.max(pct, stage.status !== 'pending' ? 2 : 0)}%`,
                    background: color,
                    opacity: stage.status === 'pending' ? 0.3 : 0.8,
                    ...(stage.status === 'pending'
                      ? { backgroundImage: `repeating-linear-gradient(90deg, ${color} 0, ${color} 4px, transparent 4px, transparent 8px)` }
                      : {}),
                  }}
                />
                {stage.status !== 'pending' && (
                  <span
                    className="absolute inset-y-0 left-2 flex items-center text-[10px] font-medium"
                    style={{ color: 'var(--text-primary)' }}
                  >
                    {formatDuration(stage.elapsed_ms)}
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
