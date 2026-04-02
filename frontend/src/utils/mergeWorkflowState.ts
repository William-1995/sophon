/**
 * Merge SSE / poll snapshots into existing WorkflowState without dropping fields.
 */

import type { GenUiPayload } from '../types'
import type { WorkflowState, WorkflowStep, TimelineEvent } from '../types/cowork'

/** ReAct / workflow store prose in `answer`; legacy UI used `report`. */
export function workflowStepMarkdownBody(
  output: Record<string, unknown> | undefined
): string | undefined {
  if (!output) return undefined
  const a = output.answer
  const r = output.report
  if (typeof a === 'string' && a.trim()) return a
  if (typeof r === 'string' && r.trim()) return r
  return undefined
}

export function workflowStepGenUi(
  output: Record<string, unknown> | undefined
): GenUiPayload | undefined {
  if (!output) return undefined
  const raw = output.gen_ui
  if (!raw || typeof raw !== 'object') return undefined
  const payload = raw as Record<string, unknown>
  if (typeof payload.type !== 'string' && typeof payload.format !== 'string') return undefined
  return payload as GenUiPayload
}

export function workflowStepArtifacts(
  output: Record<string, unknown> | undefined
): string[] {
  if (!output) return []
  const values = new Set<string>()
  const collect = (value: unknown) => {
    if (typeof value === 'string' && value.trim()) {
      values.add(value.trim())
    }
  }

  collect(output.output_file)
  if (Array.isArray(output.output_files)) {
    for (const item of output.output_files) {
      collect(item)
    }
  }
  if (Array.isArray(output.artifacts)) {
    for (const item of output.artifacts) {
      collect(item)
    }
  }

  return Array.from(values)
}

function stepSortKey(id: string): number {
  const m = /^step_(\d+)$/.exec(id)
  return m ? parseInt(m[1], 10) : 1e9
}

/** ReAct / skills may attach [{ title, url }, ...] on each step output. */
export interface WorkflowReference {
  title: string
  url: string
  step_id: string
}

function referenceDedupeKey(url: string): string {
  try {
    const u = new URL(url.trim())
    u.hash = ''
    return `${u.origin}${u.pathname}`.toLowerCase()
  } catch {
    return url.trim().toLowerCase()
  }
}

/** Merge references from all steps in execution order; dedupe by URL. */
export function aggregateWorkflowReferences(
  steps: Record<string, WorkflowStep>
): WorkflowReference[] {
  const seen = new Set<string>()
  const out: WorkflowReference[] = []
  const ordered = Object.keys(steps).sort((a, b) => stepSortKey(a) - stepSortKey(b))
  for (const stepId of ordered) {
    const raw = steps[stepId]?.output_data?.references
    if (!Array.isArray(raw)) continue
    for (const item of raw) {
      if (!item || typeof item !== 'object') continue
      const rec = item as Record<string, unknown>
      const url = typeof rec.url === 'string' ? rec.url.trim() : ''
      if (!url) continue
      const key = referenceDedupeKey(url)
      if (seen.has(key)) continue
      seen.add(key)
      const title =
        typeof rec.title === 'string' && rec.title.trim()
          ? rec.title.trim()
          : url
      out.push({ title, url, step_id: stepId })
    }
  }
  return out
}

/** Parse a single step's `output_data.references` (no cross-step dedupe). */
export function referencesFromStepOutput(
  output: Record<string, unknown> | undefined,
  stepId: string
): WorkflowReference[] {
  if (!output) return []
  const raw = output.references
  if (!Array.isArray(raw)) return []
  const out: WorkflowReference[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const rec = item as Record<string, unknown>
    const url = typeof rec.url === 'string' ? rec.url.trim() : ''
    if (!url) continue
    const title =
      typeof rec.title === 'string' && rec.title.trim()
        ? rec.title.trim()
        : url
    out.push({ title, url, step_id: stepId })
  }
  return out
}

/** Pick last step (by step_N index) that has markdown body in output_data. */
export function finalReportMarkdownFromSteps(
  steps: Record<string, WorkflowStep>
): string | undefined {
  const preferred = steps.report || steps.transform
  if (preferred?.output_data) {
    const t = workflowStepMarkdownBody(preferred.output_data as Record<string, unknown>)
    if (t) return t
  }
  const ordered = Object.keys(steps).sort((a, b) => stepSortKey(a) - stepSortKey(b))
  for (let i = ordered.length - 1; i >= 0; i--) {
    const id = ordered[i]!
    const t = workflowStepMarkdownBody(steps[id]!.output_data as Record<string, unknown>)
    if (t) return t
  }
  return undefined
}

function combineTimeline(prev: TimelineEvent[], incoming: TimelineEvent[]): TimelineEvent[] {
  const events = new Map<string, TimelineEvent>()
  prev.forEach((evt) => {
    if (evt.event_id) {
      events.set(evt.event_id, evt)
    }
  })
  incoming.forEach((evt) => {
    if (evt.event_id) {
      events.set(evt.event_id, evt)
    }
  })
  return Array.from(events.values()).sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  )
}

export function mergeWorkflowState(
  prev: WorkflowState | null,
  incoming: WorkflowState
): WorkflowState {
  if (!prev || prev.instance_id !== incoming.instance_id) {
    return incoming
  }

  const steps: Record<string, WorkflowStep> = { ...prev.steps }
  for (const [id, inc] of Object.entries(incoming.steps)) {
    const p = prev.steps[id]
    if (!p) {
      steps[id] = inc
      continue
    }
    const incOut = inc.output_data && Object.keys(inc.output_data).length > 0
    steps[id] = {
      ...p,
      ...inc,
      name:
        inc.name && inc.name !== id && inc.name !== p.step_id
          ? inc.name
          : p.name || inc.name,
      output_data: incOut ? inc.output_data : p.output_data,
      input_data: { ...p.input_data, ...inc.input_data },
    }
  }

  return {
    ...prev,
    ...incoming,
    steps,
    agents: prev.agents ?? {},
    messages: prev.messages ?? [],
    threads: prev.threads ?? {},
    timeline: combineTimeline(prev.timeline ?? [], incoming.timeline ?? []),
    batch_progress: incoming.batch_progress ?? prev.batch_progress ?? null,
    input_data: Object.keys(incoming.input_data || {}).length > 0 ? incoming.input_data : prev.input_data,
  }
}
