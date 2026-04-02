/** Workflow instance state and controls */

import { useState, useCallback } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { WorkflowState, WorkflowRunRequest } from '../types/cowork'
import {
  runWorkflow,
  pauseWorkflow,
  resumeWorkflow,
  stopWorkflow,
} from '../api/cowork'

interface UseWorkflowReturn {
  workflowState: WorkflowState | null;
  isLoading: boolean;
  error: string | null;
  run: (request: WorkflowRunRequest) => Promise<void>;
  pause: () => Promise<void>;
  resume: () => Promise<void>;
  stop: () => Promise<void>;
  setWorkflowState: Dispatch<SetStateAction<WorkflowState | null>>
}

export function useWorkflow(): UseWorkflowReturn {
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async (request: WorkflowRunRequest) => {
    setIsLoading(true)
    setError(null)

    const result = await runWorkflow(request)

    if (result.error) {
      setError(result.error)
    } else if (result.data) {
      // Fetch full instance state
      const { instance_id } = result.data
      const { getWorkflowInstance } = await import('../api/cowork')
      const stateResult = await getWorkflowInstance(instance_id)

      if (stateResult.data) {
        setWorkflowState(stateResult.data)
      }
    }

    setIsLoading(false)
  }, [])

  const pause = useCallback(async () => {
    if (!workflowState?.instance_id) return

    const result = await pauseWorkflow(workflowState.instance_id)

    if (result.error) {
      setError(result.error)
    }
  }, [workflowState?.instance_id])

  const resume = useCallback(async () => {
    if (!workflowState?.instance_id) return

    const result = await resumeWorkflow(workflowState.instance_id)

    if (result.error) {
      setError(result.error)
    }
  }, [workflowState?.instance_id])

  const stop = useCallback(async () => {
    if (!workflowState?.instance_id) return

    const result = await stopWorkflow(workflowState.instance_id)

    if (result.error) {
      setError(result.error)
    }
  }, [workflowState?.instance_id])

  return {
    workflowState,
    isLoading,
    error,
    run,
    pause,
    resume,
    stop,
    setWorkflowState,
  }
}
