/**
 * Skills and workspace API - read-only resources.
 */

import { fetchJson } from './client'
import type { Skill } from '../types'

interface SkillsResponse {
  skills?: Skill[]
}

interface WorkspaceResponse {
  files?: string[]
}

export async function fetchSkills(): Promise<Skill[]> {
  const data = await fetchJson<SkillsResponse>('/api/skills')
  return data.skills ?? []
}

export async function fetchWorkspaceFiles(): Promise<string[]> {
  const data = await fetchJson<WorkspaceResponse>('/api/workspace/files')
  return data.files ?? []
}

export interface EmotionLatest {
  emotion_label: string | null
  session_id: string | null
}

export async function fetchEmotionLatest(): Promise<EmotionLatest> {
  return fetchJson<EmotionLatest>('/api/emotion/latest')
}

export async function fetchSpeechStatus(): Promise<{ enabled: boolean }> {
  return fetchJson<{ enabled: boolean }>('/api/speech/status')
}

export async function transcribeAudio(blob: Blob): Promise<{ text: string }> {
  const form = new FormData()
  form.append('audio', blob, 'recording.webm')
  const url = `${import.meta.env.VITE_API_URL || ''}/api/speech-to-text`
  const res = await fetch(url, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const err = await res.text().catch(() => '')
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json() as Promise<{ text: string }>
}
