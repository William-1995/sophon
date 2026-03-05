/**
 * Sessions API - CRUD operations for chat sessions.
 */

import { API_BASE } from '../constants'
import { fetchJson, buildSessionsUrl } from './client'
import type { Session, TreeRoot } from '../types'

interface SessionsResponse {
  sessions?: Session[]
}

interface TreeResponse {
  roots?: TreeRoot[]
}

interface MessagesResponse {
  messages?: Array<{ role: string; content: string; references?: Array<{ title?: string; url: string }> }>
  status?: string
}

interface CreateSessionResponse {
  session_id: string
}

export async function listSessions(includeId?: string | null): Promise<Session[]> {
  const data = await fetchJson<SessionsResponse>(buildSessionsUrl(includeId))
  return data.sessions ?? []
}

export async function listSessionTree(includeId?: string | null): Promise<TreeRoot[]> {
  try {
    const data = await fetchJson<TreeResponse>(buildSessionsUrl(includeId, true))
    return data.roots ?? []
  } catch {
    return []
  }
}

export async function getMessages(sessionId: string): Promise<MessagesResponse> {
  return fetchJson<MessagesResponse>(`/api/sessions/${sessionId}/messages`)
}

export async function createSession(): Promise<string> {
  const data = await fetchJson<CreateSessionResponse>('/api/sessions', { method: 'POST' })
  return data.session_id
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function forkSession(sessionId: string): Promise<string> {
  const data = await fetchJson<CreateSessionResponse>(
    `/api/sessions/${sessionId}/fork`,
    { method: 'POST' }
  )
  return data.session_id
}
