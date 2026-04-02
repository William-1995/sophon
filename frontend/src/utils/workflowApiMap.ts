/**
 * Map GET /api/workflows/:id JSON into frontend WorkflowState (StatusMonitor).
 */

import type {
  WorkflowState,
  WorkflowStep,
  AgentState,
  WorkflowMessage,
  ThreadState,
  TimelineEvent,
} from '../types/cowork'

const STEP_STATUSES: WorkflowStep['status'][] = [
  'queued',
  'pending',
  'running',
  'paused',
  'completed',
  'failed',
  'retrying',
]

function mapStepStatus(s: string): WorkflowStep['status'] {
  return STEP_STATUSES.includes(s as WorkflowStep['status'])
    ? (s as WorkflowStep['status'])
    : 'pending'
}

const AGENT_STATUSES: AgentState['status'][] = [
  'idle',
  'working',
  'waiting',
  'dead',
]

function mapAgentStatus(s: string): AgentState['status'] {
  return AGENT_STATUSES.includes(s as AgentState['status'])
    ? (s as AgentState['status'])
    : 'idle'
}

export function mapWorkflowApiPayload(raw: Record<string, unknown>): WorkflowState {
  const steps: Record<string, WorkflowStep> = {}
  const rawSteps = raw.steps as Record<string, Record<string, unknown>> | undefined
  if (rawSteps) {
    for (const [id, s] of Object.entries(rawSteps)) {
      const sid = String(s.step_id ?? id)
      const role = s.role != null ? String(s.role) : undefined
      const execution_mode = String(s.execution_mode ?? 'tool') as WorkflowStep['execution_mode']
      steps[id] = {
        step_id: sid,
        name: String(s.name ?? sid),
        execution_mode,
        status: mapStepStatus(String(s.status ?? 'pending')),
        input_data: role ? { role } : {},
        output_data: (s.output_data as Record<string, unknown>) ?? {},
        retry_count: 0,
        convergence_status: '',
        error_message:
          s.error_message != null ? String(s.error_message) : undefined,
        agent_id: s.agent_id ? String(s.agent_id) : undefined,
        agent_ids: Array.isArray(s.agent_ids)
          ? (s.agent_ids as string[]).map(String)
          : [],
        started_at: typeof s.started_at === 'string' ? s.started_at : undefined,
        completed_at: typeof s.completed_at === 'string' ? s.completed_at : undefined,
      }
    }
  }

  const rawAgents = raw.agents as Record<string, Record<string, unknown>> | undefined
  const agents: Record<string, AgentState> = {}
  if (rawAgents) {
    for (const [id, agent] of Object.entries(rawAgents)) {
      const value = agent as Record<string, unknown>
      agents[id] = {
        agent_id: String(value.agent_id ?? id),
        agent_type: String(value.agent_type ?? ''),
        role: String(value.role ?? ''),
        status: mapAgentStatus(String(value.status ?? 'idle')),
        current_task: typeof value.current_task === 'string' ? value.current_task : undefined,
        message_count: Number(value.message_count ?? 0),
        task_count: Number(value.task_count ?? 0),
        spawned_at: String(value.spawned_at ?? ''),
        last_active: String(value.last_active ?? ''),
      }
    }
  }

  const rawMessages = raw.messages as Array<Record<string, unknown>> | undefined
  const messages: WorkflowMessage[] = []
  if (rawMessages) {
    for (const msg of rawMessages) {
      if (msg && typeof msg === 'object') {
        messages.push({
          message_id: String(msg.message_id ?? ''),
          sender: String(msg.sender ?? ''),
          receiver: msg.receiver != null ? String(msg.receiver) : undefined,
          type: String(msg.type ?? ''),
          payload: (msg.payload as Record<string, unknown>) ?? {},
          timestamp: String(msg.timestamp ?? ''),
          thread_id: msg.thread_id != null ? String(msg.thread_id) : undefined,
        })
      }
    }
  }

  const rawThreads = raw.threads as Record<string, Record<string, unknown>> | undefined
  const threads: Record<string, ThreadState> = {}
  if (rawThreads) {
    for (const [threadId, thread] of Object.entries(rawThreads)) {
      if (!thread || typeof thread !== 'object') continue
      const threadData = thread as Record<string, unknown>
      const messagesData = threadData.messages as Array<Record<string, unknown>> | undefined
    threads[threadId] = {
      thread_id: String(threadData.thread_id ?? threadId),
        topic: String(threadData.topic ?? ''),
        participant_ids: Array.isArray(threadData.participant_ids)
          ? threadData.participant_ids.map(String)
          : [],
        message_count: Number(threadData.message_count ?? 0),
        consensus_reached: Boolean(threadData.consensus_reached),
        consensus_result:
          (threadData.consensus_result as Record<string, unknown>) ?? null,
        started_at:
          typeof threadData.started_at === 'string'
            ? threadData.started_at
            : undefined,
        completed_at:
          typeof threadData.completed_at === 'string'
            ? threadData.completed_at
            : undefined,
        messages: messagesData
          ? messagesData
              .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
              .map((item) => ({
                message_id: String(item.message_id ?? ''),
                sender: String(item.sender ?? ''),
                receiver: item.receiver != null ? String(item.receiver) : undefined,
                type: String(item.type ?? ''),
                payload: (item.payload as Record<string, unknown>) ?? {},
                timestamp: String(item.timestamp ?? ''),
                thread_id: item.thread_id != null ? String(item.thread_id) : undefined,
              }))
          : [],
      }
    }
  }

  const rawTimeline = raw.timeline as Array<Record<string, unknown>> | undefined
  const timeline: TimelineEvent[] = []
  if (rawTimeline) {
    for (const item of rawTimeline) {
      if (!item || typeof item !== 'object') continue
      timeline.push({
        event_id: String(item.event_id ?? ''),
        event_type: String(item.event_type ?? ''),
        timestamp: String(item.timestamp ?? ''),
        step_id: item.step_id != null ? String(item.step_id) : undefined,
        agent_id: item.agent_id != null ? String(item.agent_id) : undefined,
        payload: (item.payload as Record<string, unknown>) ?? {},
      })
    }
  }

  const rawBatch = raw.batch_progress as Record<string, unknown> | undefined
  const batch_progress = rawBatch && typeof rawBatch === 'object' ? {
    batch_mode: Boolean(rawBatch.batch_mode),
    label: typeof rawBatch.label === 'string' ? rawBatch.label : undefined,
    total: Number(rawBatch.total ?? 0),
    completed: Number(rawBatch.completed ?? 0),
    failed: Number(rawBatch.failed ?? 0),
    current_item: typeof rawBatch.current_item === 'string' ? rawBatch.current_item : null,
    current_step_id: typeof rawBatch.current_step_id === 'string' ? rawBatch.current_step_id : null,
    current_step_name: typeof rawBatch.current_step_name === 'string' ? rawBatch.current_step_name : null,
    items_preview: Array.isArray(rawBatch.items_preview) ? rawBatch.items_preview.map(String) : [],
    items: Array.isArray(rawBatch.items) ? rawBatch.items : [],
    failures: Array.isArray(rawBatch.failures) ? rawBatch.failures : [],
    batch_contract: typeof rawBatch.batch_contract === 'string' ? rawBatch.batch_contract : undefined,
    status: typeof rawBatch.status === 'string' ? rawBatch.status : undefined,
  } : undefined

  const rawInput = raw.input_data as Record<string, unknown> | undefined
  const input_data = rawInput && typeof rawInput === 'object' ? rawInput : {}

  const st = String(raw.status ?? 'queued')
  const status: WorkflowState['status'] =
    st === 'queued' ||
    st === 'running' ||
    st === 'paused' ||
    st === 'completed' ||
    st === 'failed'
      ? st
      : 'queued'

  return {
    workflow_id: String(raw.workflow_id ?? 'workflow'),
    instance_id: String(raw.instance_id ?? ''),
    status,
    steps,
    current_step_id:
      raw.current_step_id != null ? String(raw.current_step_id) : undefined,
    agents,
    messages,
    threads,
    batch_progress,
    input_data,
    created_at: String(raw.created_at ?? ''),
    started_at:
      raw.started_at != null ? String(raw.started_at) : undefined,
    completed_at:
      raw.completed_at != null ? String(raw.completed_at) : undefined,
    error_message:
      raw.error_message != null ? String(raw.error_message) : undefined,
  }
}
