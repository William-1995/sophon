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
  cancelled?: boolean
}

export async function sendAsync(
  message: string,
  skill: string | null,
  sessionId: string,
  uploadedFiles: string[] = []
): Promise<{ child_session_id?: string }> {
  const res = await fetch(`${API_BASE}/api/chat/async`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, skill, session_id: sessionId, uploaded_files: uploadedFiles }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function cancelRun(runId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/runs/${runId}/cancel`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function submitDecision(
  runId: string,
  choice: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/runs/${runId}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ choice }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export interface DecisionRequired {
  runId: string
  message?: string
  choices?: string[]
  payload?: Record<string, unknown>
}

export async function sendStream(
  message: string,
  skill: string | null,
  sessionId: string,
  onProgress: (tokens: number) => void,
  onChunk: (data: Record<string, unknown>) => void,
  onRunStarted?: (runId: string) => void,
  onDecisionRequired?: (data: DecisionRequired) => void,
  resumeRunId?: string | null,
  uploadedFiles: string[] = []
): Promise<StreamResult> {
  const body: Record<string, unknown> = {
    message: resumeRunId ? '[Resume]' : message,
    skill,
    session_id: sessionId,
  }
  if (resumeRunId) body.resume_run_id = resumeRunId
  if (uploadedFiles.length > 0) body.uploaded_files = uploadedFiles
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
  let finalCancelled = false

  const processEvent = (data: Record<string, unknown>) => {
    const type = String(data.type ?? '')
    if (type === 'RUN_STARTED' && typeof data.runId === 'string') {
      onRunStarted?.(data.runId)
    } else if (type === 'CUSTOM') {
      const value = data.value as Record<string, unknown> | undefined
      if (data.name === 'progress' && value && typeof value.tokens === 'number') onProgress(value.tokens)
      if (data.name === 'gen_ui') finalGenUi = value as Message['genUi']
    } else if (type === 'TEXT_MESSAGE_CONTENT' && typeof data.delta === 'string') {
      finalAnswer += data.delta
    } else if (type === 'RUN_CANCELLED') {
      finalCancelled = true
    } else if (type === 'RUN_FINISHED') {
      const result = (data.result ?? {}) as Record<string, unknown>
      finalSessionId = (result.session_id as string) ?? sessionId
      finalTokens = (result.tokens as number) ?? 0
      finalCacheHit = (result.cache_hit as boolean) ?? false
      finalCancelled = (result.cancelled as boolean) ?? false
      if (result.gen_ui != null) finalGenUi = result.gen_ui as Message['genUi']
      if (Array.isArray(result.references)) finalReferences = result.references as Reference[]
    } else if (type === 'RUN_ERROR') {
      throw new Error((data.message as string) ?? 'Unknown error')
    } else if (type === 'DECISION_REQUIRED' || (type === 'CUSTOM' && data.name === 'decision_required')) {
      const value = (data.value ?? data) as Record<string, unknown>
      onDecisionRequired?.({
        runId: (value.runId ?? data.runId ?? '') as string,
        message: (value.message ?? value.prompt) as string | undefined,
        choices: Array.isArray(value.choices) ? (value.choices as string[]) : undefined,
        payload: (value.payload as Record<string, unknown> | undefined) ?? undefined,
      })
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
    cancelled: finalCancelled,
    genUi: finalGenUi,
    references: finalReferences,
  }
}
