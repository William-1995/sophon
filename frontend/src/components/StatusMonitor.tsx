import React, { useMemo } from 'react'
import type { WorkflowState } from '../types/cowork'
import { finalReportMarkdownFromSteps, workflowStepArtifacts } from '../utils/mergeWorkflowState'
import { RuntimeControls } from './RuntimeControls'
import {
  deriveWorkflowPhase,
  formatDuration,
  formatTimestamp,
  type WorkflowPhaseCard,
  describeWorkflowRequest,
} from './workflow/workflowView'
import type { SteeringNote } from './workflow/StatusMonitorParts'
import {
  BatchProgressPanel,
  FinalReportPanel,
  StepCard,
  SteeringPanel,
  WorkflowPhaseRail,
} from './workflow/StatusMonitorParts'

export type { SteeringNote }

interface StatusMonitorProps {
  workflowState: WorkflowState
  onPause: () => void
  onResume: () => void
  onStop: () => void
  isLoading?: boolean
  steeringLog?: SteeringNote[]
  onSteeringSubmit?: (text: string) => void
}

export const StatusMonitor: React.FC<StatusMonitorProps> = ({
  workflowState,
  onPause,
  onResume,
  onStop,
  isLoading,
  steeringLog = [],
  onSteeringSubmit,
}) => {
  const steps = useMemo(() => Object.values(workflowState.steps), [workflowState.steps])
  const completedCount = useMemo(
    () => steps.filter((step) => step.status === 'completed').length,
    [steps]
  )
  const timeline = useMemo(
    () =>
      [...(workflowState.timeline || [])].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      ),
    [workflowState.timeline]
  )
  const phase = useMemo(
    () => deriveWorkflowPhase(workflowState, steps, timeline),
    [workflowState, steps, timeline]
  )
  const narrative = useMemo(() => {
    if (workflowState.status === 'running') {
      const current = steps.find((step) => step.step_id === workflowState.current_step_id)
      return `Running ${current?.name || workflowState.current_step_id || 'workflow'} · ${completedCount}/${steps.length}`
    }
    if (workflowState.status === 'completed') {
      return `Completed in ${formatDuration(workflowState.started_at, workflowState.completed_at)}`
    }
    if (workflowState.status === 'failed') {
      return `Failed · ${workflowState.error_message || 'Check step cards for details'}`
    }
    return `${workflowState.status} · ${completedCount}/${steps.length} ready`
  }, [workflowState, steps, completedCount])

  const finalReport = useMemo(
    () => finalReportMarkdownFromSteps(workflowState.steps),
    [workflowState.steps]
  )
  const artifactFiles = useMemo(
    () =>
      Array.from(
        new Set(
          Object.values(workflowState.steps).flatMap((step) =>
            workflowStepArtifacts(step.output_data as Record<string, unknown>)
          )
        )
      ),
    [workflowState.steps]
  )
  const requestText = useMemo(
    () => describeWorkflowRequest(workflowState.input_data),
    [workflowState.input_data]
  )

  const isRunning = workflowState.status === 'running'
  const durationLabel = useMemo(() => {
    if (workflowState.status === 'running') {
      return workflowState.started_at
        ? `Started ${formatTimestamp(workflowState.started_at)}`
        : 'Running'
    }
    if (workflowState.status === 'completed' && workflowState.started_at) {
      return `Completed in ${formatDuration(workflowState.started_at, workflowState.completed_at)}`
    }
    if (workflowState.status === 'failed' && workflowState.started_at) {
      return `Stopped after ${formatDuration(workflowState.started_at, workflowState.completed_at)}`
    }
    return ''
  }, [workflowState])

  return (
    <div className="status-monitor">
      {requestText && (
        <section className="workflow-request-card" aria-label="Current workflow request">
          <div className="workflow-request-card__label">Current request</div>
          <div className="workflow-request-card__body">{requestText}</div>
        </section>
      )}
      <div className="monitor-header">
        <div className="workflow-info">
          <h2>{workflowState.workflow_id}</h2>
          <p className="workflow-narrative-text">{narrative}</p>
          <WorkflowPhaseRail phase={phase as WorkflowPhaseCard} />
          <p className="workflow-phase-strip__hint">{phase.hint}</p>
          <BatchProgressPanel progress={workflowState.batch_progress} />
          <div className="meta-info">
            <span className={`status-badge status-${workflowState.status}`}>
              {workflowState.status}
            </span>
            <span className="instance-id">{workflowState.instance_id}</span>
            {durationLabel ? (
              <span className="duration">{durationLabel}</span>
            ) : null}
          </div>
          {workflowState.error_message && (
            <p className="workflow-error-message">{workflowState.error_message}</p>
          )}
        </div>
        <RuntimeControls
          status={workflowState.status}
          onPause={onPause}
          onResume={onResume}
          onStop={onStop}
          isLoading={isLoading}
        />
      </div>

      <div className="workflow-body">
        <section className="steps-panel">
          <div className="workflow-panel__header steps-panel__header">
            <h3>Steps ({completedCount}/{steps.length})</h3>
          </div>
          <div className="steps-grid">
            {steps.map((step, index) => (
              <StepCard
                key={step.step_id}
                step={step}
                index={index}
                isActive={step.step_id === workflowState.current_step_id}
              />
            ))}
          </div>
        </section>

        <FinalReportPanel report={finalReport} artifactFiles={artifactFiles} />

      </div>

      <SteeringPanel
        isRunning={isRunning}
        steeringLog={steeringLog}
        onSteeringSubmit={onSteeringSubmit}
      />
    </div>
  )
}

export default StatusMonitor
