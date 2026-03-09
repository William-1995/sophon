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
