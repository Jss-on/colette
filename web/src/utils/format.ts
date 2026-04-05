export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remaining = seconds % 60
  if (minutes < 60) return `${minutes}m ${remaining}s`
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return `${hours}h ${remainingMinutes}m`
}

export function formatTokens(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`
  return `${(n / 1_000_000).toFixed(1)}M`
}

export function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
