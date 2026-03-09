/**
 * Session ID display utilities.
 */

import { SESSION_ID_PREFIX, SESSION_ID_DISPLAY_LEN } from '../constants'

export function formatSessionId(id: string | null): string {
  if (!id) return '—'
  return id.replace(new RegExp(`^${SESSION_ID_PREFIX}`), '').slice(0, SESSION_ID_DISPLAY_LEN)
}
