/**
 * SSE EventSource hook - subscribes to /api/events for task lifecycle.
 */

import { useEffect, useRef } from 'react'
import { API_BASE } from '../constants'

type RefreshFn = () => void

interface UseEventSourceOptions {
  onTaskEvent?: (type: string, data: Record<string, unknown>) => void
  onRefreshTree?: RefreshFn
  onRefreshSessions?: RefreshFn
  onRefreshMessages?: (sessionId: string) => void
  currentSessionId: string | null
}

export function useEventSource({
  onTaskEvent,
  onRefreshTree,
  onRefreshSessions,
  onRefreshMessages,
  currentSessionId,
}: UseEventSourceOptions): void {
  const sessionIdRef = useRef<string | null>(null)
  useEffect(() => {
    sessionIdRef.current = currentSessionId
  }, [currentSessionId])

  useEffect(() => {
    const url = `${API_BASE}/api/events`
    const es = new EventSource(url)

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as Record<string, unknown>
        const type = String(data.type ?? '')
        if (type === 'heartbeat') return

        if (type === 'TASK_STARTED' || type === 'TASK_FINISHED' || type === 'TASK_ERROR') {
          onRefreshTree?.()
          onRefreshSessions?.()
          const tid = data.threadId as string | undefined
          if (tid && tid === sessionIdRef.current) {
            onRefreshMessages?.(tid)
          }
        }
        if (type === 'TASK_FINISHED') {
          const label = (data.label as string) || 'Task finished'
          if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification('Sophon', { body: label })
          }
        }
        if (type === 'TASK_ERROR') {
          const msg = (data.message as string) || 'Task failed'
          if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification('Sophon Error', { body: msg })
          }
        }
        onTaskEvent?.(type, data)
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      es.close()
    }

    return () => {
      es.close()
    }
  }, [onTaskEvent, onRefreshTree, onRefreshSessions, onRefreshMessages])
}
