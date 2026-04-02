/** Workflow runtime API client */

import type {
  WorkflowState,
  WorkflowRunRequest,
  WorkflowRunResponse,
  ApiResponse,
} from '../types/cowork';
import { mapWorkflowApiPayload } from '../utils/workflowApiMap';

const API_BASE = '/api';

/** Start a workflow run */
export async function runWorkflow(
  request: WorkflowRunRequest
): Promise<ApiResponse<WorkflowRunResponse>> {
  try {
    const response = await fetch(`${API_BASE}/workflows/${request.workflow_id}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input_data: request.input_data,
        auto_execute: request.auto_execute ?? true,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      return { error };
    }

    const data = await response.json();
    return { data };
  } catch (err) {
    return { error: err instanceof Error ? err.message : 'Unknown error' };
  }
}

export async function getWorkflowInstance(
  instanceId: string
): Promise<ApiResponse<WorkflowState>> {
  try {
    const response = await fetch(`${API_BASE}/workflows/${instanceId}`);

    if (!response.ok) {
      const error = await response.text();
      return { error };
    }

    const raw = (await response.json()) as Record<string, unknown>;
    return { data: mapWorkflowApiPayload(raw) };
  } catch (err) {
    return { error: err instanceof Error ? err.message : 'Unknown error' };
  }
}

/** Pause instance */
export async function pauseWorkflow(instanceId: string): Promise<ApiResponse<void>> {
  try {
    const response = await fetch(`${API_BASE}/instances/${instanceId}/pause`, {
      method: 'POST',
    });

    if (!response.ok) {
      const error = await response.text();
      return { error };
    }

    return {};
  } catch (err) {
    return { error: err instanceof Error ? err.message : 'Unknown error' };
  }
}

/** Resume instance */
export async function resumeWorkflow(instanceId: string): Promise<ApiResponse<void>> {
  try {
    const response = await fetch(`${API_BASE}/instances/${instanceId}/resume`, {
      method: 'POST',
    });

    if (!response.ok) {
      const error = await response.text();
      return { error };
    }

    return {};
  } catch (err) {
    return { error: err instanceof Error ? err.message : 'Unknown error' };
  }
}

/** Stop instance */
export async function stopWorkflow(instanceId: string): Promise<ApiResponse<void>> {
  try {
    const response = await fetch(`${API_BASE}/instances/${instanceId}/stop`, {
      method: 'POST',
    });

    if (!response.ok) {
      const error = await response.text();
      return { error };
    }

    return {};
  } catch (err) {
    return { error: err instanceof Error ? err.message : 'Unknown error' };
  }
}

/** List all workflow instances */
export async function listInstances(): Promise<ApiResponse<{ instances: Array<{ instance_id: string; workflow_id: string; status: string; error_message?: string; created_at: string }> }>> {
  try {
    const response = await fetch(`${API_BASE}/workflows/`);
    
    if (!response.ok) {
      const error = await response.text();
      return { error };
    }

    const data = await response.json();
    return { data };
  } catch (err) {
    return { error: err instanceof Error ? err.message : 'Unknown error' };
  }
}