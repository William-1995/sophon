/**
 * API client - base fetcher and URL builder.
 * Single responsibility: HTTP communication.
 */

import { API_BASE } from '../constants'

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const res = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function buildSessionsUrl(includeId?: string | null, tree = false): string {
  const params = new URLSearchParams()
  if (tree) params.set('tree', '1')
  if (includeId) params.set('include', includeId)
  const qs = params.toString()
  return `/api/sessions${qs ? `?${qs}` : ''}`
}
