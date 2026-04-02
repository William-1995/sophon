/** Workflow runtime types (align with backend models) */

// Message bus
export interface Message {
  message_id: string;
  sender: string;
  receiver?: string;
  type: 'task' | 'result' | 'critique' | 'consensus' | 'broadcast' | 'direct';
  payload: Record<string, unknown>;
  timestamp: string;
  thread_id?: string;
}

export interface WorkflowMessage {
  message_id: string;
  sender: string;
  receiver?: string;
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
  thread_id?: string;
}

export interface TimelineEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  step_id?: string;
  agent_id?: string;
  payload: Record<string, unknown>;
}

export interface WorkflowBatchProgress {
  batch_mode?: boolean;
  label?: string;
  total?: number;
  completed?: number;
  failed?: number;
  current_item?: string | null;
  current_step_id?: string | null;
  current_step_name?: string | null;
  items_preview?: string[];
  items?: unknown[];
  failures?: unknown[];
  batch_contract?: string;
  status?: string;
}

// Agent
export interface AgentState {
  agent_id: string;
  agent_type: string;
  role: string;
  status: 'idle' | 'working' | 'waiting' | 'dead';
  current_task?: string;
  message_count: number;
  task_count: number;
  spawned_at: string;
  last_active: string;
}

// Workflow
export interface WorkflowStep {
  step_id: string;
  name: string;
  execution_mode: 'tool' | 'agent' | 'multi_agent' | 'discussion';
  status: 'queued' | 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'retrying';
  agent_id?: string;
  agent_ids?: string[];
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  retry_count: number;
  convergence_status: string;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
}

export interface WorkflowState {
  workflow_id: string;
  instance_id: string;
  status: 'queued' | 'running' | 'paused' | 'completed' | 'failed';
  steps: Record<string, WorkflowStep>;
  current_step_id?: string;
  agents: Record<string, AgentState>;
  messages: WorkflowMessage[];
  threads: Record<string, ThreadState>;
  timeline: TimelineEvent[];
  batch_progress?: WorkflowBatchProgress | null;
  input_data: Record<string, unknown>;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface ThreadState {
  thread_id: string;
  topic: string;
  participant_ids: string[];
  message_count: number;
  consensus_reached: boolean;
  consensus_result?: Record<string, unknown> | null;
  started_at?: string;
  completed_at?: string;
  messages?: WorkflowMessage[];
}

// API wrapper
export interface ApiResponse<T> {
  data?: T;
  error?: string;
}

export interface WorkflowRunRequest {
  workflow_id: string;
  input_data: Record<string, unknown>;
  auto_execute?: boolean;
}

export interface WorkflowRunResponse {
  instance_id: string;
  status: string;
}
