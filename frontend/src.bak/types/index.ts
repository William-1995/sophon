/**
 * Shared type definitions.
 * Single source of truth for domain models.
 */

export interface Skill {
  name: string
  description: string
}

export interface Session {
  id: string
  message_count: number
  updated_at: number | null
}

export interface ChildSession {
  session_id: string
  parent_id: string | null
  title: string
  agent: string
  kind: string
  status: string
  created_at: number
  updated_at: number
}

export interface TreeRoot {
  id: string
  message_count: number
  updated_at: number | null
  children: ChildSession[]
}

export interface Reference {
  title?: string
  url: string
}

export interface GenUiPayload {
  type?: string
  format?: string
  payload?: unknown
  messages?: unknown[]
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  skill?: string
  cacheHit?: boolean
  tokens?: number
  genUi?: { type: string; payload?: unknown }
  references?: Reference[]
}

export type SendMode = 'async' | 'sync'

export type ResizeCorner = 'se' | 'sw' | 'ne' | 'nw'
