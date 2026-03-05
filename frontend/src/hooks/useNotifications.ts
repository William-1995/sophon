/**
 * Request notification permission on mount.
 */

import { useEffect } from 'react'

export function useNotifications(): void {
  useEffect(() => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])
}
