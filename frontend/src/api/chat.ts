/**
 * Chat API - send messages (sync stream, async).
 */

import { API_BASE } from '../constants'
import type { Message, Reference } from '../types'

export interface StreamResult {
  sessionId: string
  content: string
  tokens: number
  cacheHit: boolean
  genUi?: Message['genUi']
  references: Reference[]
}

export async function sendAsync(
  message: string,
  skill: string | null,
  sessionId: string
): Promise<{ child_session_id?: string }> {
  const res = await fetch(`${API_BASE}/api/chat/async`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, skill, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function sendStream(
  message: string,
  skill: string | null,
  sessionId: string,
  onProgress: (tokens: number) => void,
  onChunk: (data: Record<string, unknown>) => void
): Promise<StreamResult> {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, skill, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  if (!res.body) throw new Error('No response body')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalAnswer = ''
  let finalTokens = 0
  let finalCacheHit = false
  let finalGenUi: Message['genUi'] = undefined
  let finalReferences: Reference[] = []
  let finalSessionId = sessionId

  const processEvent = (data: Record<string, unknown>) => {
    const type = String(data.type ?? '')
    if (type === 'CUSTOM') {
      const value = data.value as Record<string, unknown> | undefined
      if (value && typeof value.tokens === 'number') onProgress(value.tokens)
      if (data.name === 'gen_ui') finalGenUi = value as Message['genUi']
    } else if (type === 'TEXT_MESSAGE_CONTENT' && typeof data.delta === 'string') {
      finalAnswer += data.delta
    } else if (type === 'RUN_FINISHED') {
      const result = (data.result ?? {}) as Record<string, unknown>
      finalSessionId = (result.session_id as string) ?? sessionId
      finalTokens = (result.tokens as number) ?? 0
      finalCacheHit = (result.cache_hit as boolean) ?? false
      if (result.gen_ui != null) finalGenUi = result.gen_ui as Message['genUi']
      if (Array.isArray(result.references)) finalReferences = result.references as Reference[]
    } else if (type === 'RUN_ERROR') {
      throw new Error((data.message as string) ?? 'Unknown error')
    }
    if (type === 'progress' && typeof data.tokens === 'number') onProgress(data.tokens)
    if (type === 'done') {
      finalAnswer = (data.answer as string) ?? ''
      finalSessionId = (data.session_id as string) ?? sessionId
      finalTokens = (data.tokens as number) ?? 0
      finalCacheHit = (data.cache_hit as boolean) ?? false
      finalGenUi = data.gen_ui as Message['genUi'] | undefined
      if (Array.isArray(data.references)) finalReferences = data.references as Reference[]
    }
    if (type === 'error') throw new Error((data.error as string) ?? 'Unknown error')
    onChunk(data)
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const block of parts) {
      if (block.indexOf('data: ') !== 0) continue
      try {
        const data = JSON.parse(block.slice(6)) as Record<string, unknown>
        processEvent(data)
      } catch (e) {
        if (e instanceof SyntaxError) continue
        throw e
      }
    }
  }
  if (buffer && buffer.indexOf('data: ') === 0) {
    try {
      const data = JSON.parse(buffer.slice(6)) as Record<string, unknown>
      processEvent(data)
    } catch (e) {
      if (!(e instanceof SyntaxError)) throw e
    }
  }

  return {
    sessionId: finalSessionId,
    content: finalAnswer,
    tokens: finalTokens,
    cacheHit: finalCacheHit,
    genUi: finalGenUi,
    references: finalReferences,
  }
}
