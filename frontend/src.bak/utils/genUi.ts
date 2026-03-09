/**
 * GenUI storage utilities - persist/restore gen_ui per session.
 */

import { GEN_UI_PREFIX } from '../constants'
import type { Message } from '../types'

function isValidGenUi(v: unknown): v is { type: string; payload?: unknown } {
  return (
    v != null &&
    typeof v === 'object' &&
    'type' in v &&
    (v as { payload?: unknown }).payload != null
  )
}

export function loadGenUiForMessages(
  sessionId: string,
  baseMsgs: Array<{ role: string; content: string; references?: Message['references'] }>
): Message[] {
  try {
    const stored = localStorage.getItem(GEN_UI_PREFIX + sessionId)
    const genUiMap: Record<string, unknown> = stored ? JSON.parse(stored) : {}
    let ai = 0
    return baseMsgs.map((m) => {
      if (m.role !== 'assistant') return { ...m, role: m.role as 'user' | 'assistant' }
      const gu = genUiMap[String(ai)]
      ai += 1
      return {
        ...m,
        role: 'assistant' as const,
        genUi: isValidGenUi(gu) ? gu : undefined,
      }
    }) as Message[]
  } catch {
    return baseMsgs as Message[]
  }
}

export function saveGenUi(sessionId: string, assistantIndex: number, genUi: Message['genUi']): void {
  if (!genUi || !sessionId) return
  try {
    const prev = localStorage.getItem(GEN_UI_PREFIX + sessionId)
    const map: Record<string, unknown> = prev ? JSON.parse(prev) : {}
    map[String(assistantIndex)] = genUi
    localStorage.setItem(GEN_UI_PREFIX + sessionId, JSON.stringify(map))
  } catch {
    // ignore storage errors
  }
}
