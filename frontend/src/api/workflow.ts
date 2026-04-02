const API_BASE = '/api/workflows'

export interface CreateWorkflowResponse {
  instance_id: string
}

export async function createWorkflowFromText(
  description: string,
  uploadedFiles: string[] = []
): Promise<CreateWorkflowResponse> {
  const response = await fetch(`${API_BASE}/create-from-text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description, uploaded_files: uploadedFiles }),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(
      (err as { detail?: string }).detail || 'Failed to create workflow'
    )
  }

  return response.json()
}

export async function executeWorkflow(instanceId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${instanceId}/execute`, {
    method: 'POST',
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(
      (err as { detail?: string }).detail || 'Failed to execute workflow'
    )
  }
}

export function createWorkflowStream(instanceId: string): EventSource {
  return new EventSource(`${API_BASE}/${instanceId}/stream`)
}
