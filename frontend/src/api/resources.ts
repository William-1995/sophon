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

export interface WorkspaceUploadResult {
  saved: string[]
  errors?: { name: string; error: string }[]
}

function toFileArray(files: File | File[] | FileList): File[] {
  if (files instanceof File) return [files]
  return Array.from(files)
}

/**
 * Upload one or more files into workspace/{user}/<subdir>/ (default docs).
 */
export async function uploadWorkspaceFiles(
  files: File | File[] | FileList,
  subdir = 'docs',
): Promise<WorkspaceUploadResult> {
  const form = new FormData()
  form.append('subdir', subdir)
  for (const f of toFileArray(files)) {
    form.append('files', f, f.name)
  }
  const base = import.meta.env.VITE_API_URL || ''
  const url = `${base}/api/workspace/upload`
  const res = await fetch(url, { method: 'POST', body: form })
  const raw = await res.text()
  type ErrBody = WorkspaceUploadResult & { detail?: unknown }
  let data: ErrBody = { saved: [] }
  try {
    if (raw) data = JSON.parse(raw) as ErrBody
  } catch {
    /* non-JSON error body */
  }
  if (!res.ok) {
    const detail = data.detail
    let msg: string
    if (typeof detail === 'string') msg = detail
    else if (Array.isArray(detail))
      msg = detail.map((d: { msg?: string }) => d?.msg ?? JSON.stringify(d)).join('; ')
    else msg = raw?.slice(0, 200) || `HTTP ${res.status}`
    throw new Error(msg)
  }
  return { saved: data.saved ?? [], errors: data.errors }
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


export interface WorkspaceDownloadResult {
  ok: boolean
  filename: string
}

function sanitizeArchiveName(name: string): string {
  const base = (name || 'workspace-files.zip').replace(/[\/]+/g, '_').trim()
  return base.endsWith('.zip') ? base : `${base}.zip`
}

export async function downloadWorkspaceFiles(
  files: string[],
  archiveName = 'workspace-files.zip',
): Promise<WorkspaceDownloadResult> {
  if (files.length === 0) {
    throw new Error('No files selected')
  }
  const params = new URLSearchParams()
  for (const file of files) params.append('files', file)
  params.set('archive_name', sanitizeArchiveName(archiveName))
  const base = import.meta.env.VITE_API_URL || ''
  const url = `${base}/api/workspace/download?${params.toString()}`
  const res = await fetch(url)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `HTTP ${res.status}`)
  }
  const blob = await res.blob()
  const disposition = res.headers.get('content-disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  const filename = match?.[1] || sanitizeArchiveName(archiveName)
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
  return { ok: true, filename }
}
