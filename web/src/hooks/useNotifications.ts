import { useEffect, useRef } from 'react'
import { useDecisionStore } from '../stores/decisions'

export function useNotifications() {
  const entries = useDecisionStore((s) => s.entries)
  const prevCountRef = useRef(entries.length)

  useEffect(() => {
    if (entries.length <= prevCountRef.current) {
      prevCountRef.current = entries.length
      return
    }

    const newEntries = entries.slice(0, entries.length - prevCountRef.current)
    prevCountRef.current = entries.length

    for (const entry of newEntries) {
      if (entry.type === 'approval_required' && 'Notification' in window) {
        if (Notification.permission === 'granted') {
          new Notification('Colette: Approval Required', {
            body: `${entry.stage} gate needs your review: ${entry.detail}`,
            icon: '/icons.svg',
          })
        } else if (Notification.permission !== 'denied') {
          Notification.requestPermission()
        }
      }
    }
  }, [entries])
}
