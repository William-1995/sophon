import type { TimelineEvent, WorkflowState, WorkflowStep } from '../../types/cowork'

export interface WorkflowStageBanner {
  label: string
  hint: string
}

export interface WorkflowPhaseCard {
  key: 'investigating' | 'clarifying' | 'planning' | 'executing' | 'finalizing' | 'blocked'
  label: string
  hint: string
}

export const WORKFLOW_PHASE_ORDER: WorkflowPhaseCard['key'][] = [
  'investigating',
  'clarifying',
  'planning',
  'executing',
  'finalizing',
]

export const WORKFLOW_PHASE_LABELS: Record<WorkflowPhaseCard['key'], string> = {
  investigating: 'Investigating',
  clarifying: 'Clarifying',
  planning: 'Planning',
  executing: 'Executing',
  finalizing: 'Finalizing',
  blocked: 'Blocked',
}

export function describeWorkflowStage(
  workflowState: WorkflowState | null,
  isCreating: boolean,
  pendingGoal: string | null,
): WorkflowStageBanner {
  if (isCreating) {
    return {
      label: 'Investigating',
      hint: pendingGoal
        ? `Understanding your goal: ${pendingGoal}`
        : 'Understanding the request, finding relevant files, and preparing the plan.',
    }
  }
  if (!workflowState) {
    return { label: '', hint: '' }
  }
  if (workflowState.status === 'queued') {
    return { label: 'Planning', hint: 'The workflow is gathering context and building a plan.' }
  }
  if (workflowState.status === 'running') {
    return { label: 'Executing', hint: '' }
  }
  if (workflowState.status === 'paused') {
    return {
      label: 'Waiting',
      hint: 'The workflow is paused and waiting for input or confirmation.',
    }
  }
  if (workflowState.status === 'completed') {
    return {
      label: 'Completed',
      hint: 'The workflow finished successfully. You can review the latest report or start a new run.',
    }
  }
  if (workflowState.status === 'failed') {
    return {
      label: 'Failed',
      hint: workflowState.error_message || 'The workflow failed. Check the step cards and timeline.',
    }
  }
  return { label: workflowState.status, hint: 'Monitoring workflow progress.' }
}

export function deriveWorkflowPhase(
  workflowState: WorkflowState,
  steps: WorkflowStep[],
  timeline: TimelineEvent[],
): WorkflowPhaseCard {
  const current = workflowState.current_step_id
    ? workflowState.steps[workflowState.current_step_id]
    : undefined
  const lastEvent = timeline[timeline.length - 1]
  const lastType = lastEvent?.event_type || ''

  if (workflowState.status === 'failed') {
    return {
      key: 'blocked',
      label: 'Blocked',
      hint: workflowState.error_message || 'The workflow stopped because a step failed.',
    }
  }
  if (workflowState.status === 'completed') {
    return {
      key: 'finalizing',
      label: 'Finalizing',
      hint: 'All steps are complete and the final report is ready.',
    }
  }
  if (workflowState.status === 'paused') {
    return {
      key: 'clarifying',
      label: 'Clarifying',
      hint: 'Waiting for the next user input or confirmation before continuing.',
    }
  }
  if (current && current.status === 'running') {
    return {
      key: 'executing',
      label: 'Executing',
      hint: `Working on ${current.name || current.step_id}.`,
    }
  }
  if (lastType === 'step_started' || lastType === 'step_completed') {
    return {
      key: 'executing',
      label: 'Executing',
      hint: 'A step just moved forward and the workflow is actively processing it.',
    }
  }
  if (lastType === 'workflow_created' || lastType === 'workflow_started' || workflowState.status === 'queued') {
    return {
      key: 'planning',
      label: 'Planning',
      hint: 'The workflow is gathering context and shaping the task into steps.',
    }
  }
  if (steps.some((step) => step.status === 'pending' || step.status === 'queued')) {
    return {
      key: 'investigating',
      label: 'Investigating',
      hint: 'The workflow is still figuring out the right path and available inputs.',
    }
  }
  return {
    key: 'executing',
    label: 'Executing',
    hint: 'The workflow is actively moving through its steps.',
  }
}

export function isRecentlyActive(lastActive?: string): boolean {
  if (!lastActive) return false
  const ts = new Date(lastActive).getTime()
  return Number.isFinite(ts) && Date.now() - ts < 15_000
}

export const formatDuration = (start?: string, end?: string): string => {
  if (!start) return '-'
  const begin = new Date(start).getTime()
  const finish = end ? new Date(end).getTime() : Date.now()
  const delta = Math.max(0, Math.floor((finish - begin) / 1000))
  const mins = Math.floor(delta / 60)
  const secs = delta % 60
  return `${mins}m ${secs}s`
}

export const formatTimestamp = (iso?: string): string =>
  iso ? new Date(iso).toLocaleTimeString('zh-CN', { hour12: false }) : ''

export const getStepNote = (step: WorkflowStep, isActive: boolean): string => {
  if (step.status === 'failed') return 'Blocked — review the timeline for details.'
  if (step.status === 'completed') return 'Phase complete.'
  if (step.status === 'running' || isActive) return 'Working on this phase now.'
  if (step.status === 'queued') return 'Queued for investigation or planning.'
  if (step.status === 'paused') return 'Waiting for clarification.'
  if (step.status === 'retrying') return 'Retrying with a lighter pass.'
  return 'Awaiting phase update.'
}

const EVENT_LABELS: Record<string, string> = {
  workflow_created: 'Workflow scheduled',
  workflow_started: 'Execution started',
  workflow_completed: 'Workflow completed',
  workflow_failed: 'Workflow failed',
  step_started: 'Step started',
  step_completed: 'Step completed',
  step_failed: 'Step failed',
  agent_message: 'Agent message',
}

export const getEventLabel = (event: TimelineEvent): string =>
  EVENT_LABELS[event.event_type] || event.event_type.replace(/_/g, ' ')

export const getEventDetail = (event: TimelineEvent): string => {
  const payload = event.payload || {}
  if (typeof payload.text === 'string' && payload.text.trim()) {
    return payload.text.trim()
  }
  if (typeof payload.summary === 'string') {
    return payload.summary
  }
  if (event.event_type === 'step_started') {
    return `Step ${event.step_id} is running`
  }
  if (event.event_type === 'step_failed') {
    return `Step ${event.step_id} reported an error`
  }
  return JSON.stringify(payload).slice(0, 120) || '—'
}


export function describeWorkflowRequest(inputData: Record<string, unknown> | undefined): string {
  if (!inputData || typeof inputData !== 'object') return ''
  const candidates = [
    inputData.description,
    inputData.goal,
    inputData.task,
    inputData.question,
    inputData.prompt,
    inputData.user_goal,
  ]
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim()
    }
  }
  const data = inputData.data
  if (typeof data === 'string' && data.trim()) {
    return data.trim()
  }
  if (data && typeof data === 'object') {
    try {
      return JSON.stringify(data, null, 2)
    } catch {
      return ''
    }
  }
  try {
    const fallback = JSON.stringify(inputData, null, 2)
    return fallback === '{}' ? '' : fallback
  } catch {
    return ''
  }
}
