import React, { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { AgentState, TimelineEvent, WorkflowState, WorkflowStep, WorkflowBatchProgress } from '../../types/cowork'
import { GenUiChart } from '../GenUiChart/GenUiChart'
import { downloadWorkspaceFiles } from '../../api/resources'
import { workflowStepArtifacts, workflowStepGenUi, workflowStepMarkdownBody } from '../../utils/mergeWorkflowState'
import type { GenUiPayload } from '../../types'
import {
  WORKFLOW_PHASE_LABELS,
  WORKFLOW_PHASE_ORDER,
  type WorkflowPhaseCard,
  formatDuration,
  formatTimestamp,
  getEventDetail,
  getEventLabel,
  getStepNote,
  isRecentlyActive,
} from './workflowView'

export interface SteeringNote {
  id: string
  text: string
  at: string
}

export const STEP_STATUS_LABELS: Record<WorkflowStep['status'], string> = {
  queued: 'Queued',
  running: 'In Progress',
  paused: 'Paused',
  completed: 'Completed',
  failed: 'Failed',
  retrying: 'Retrying',
}

export const WorkflowPhaseRail: React.FC<{ phase: WorkflowPhaseCard }> = ({ phase }) => {
  const activeIndex = WORKFLOW_PHASE_ORDER.indexOf(phase.key)

  return (
    <div className="workflow-phase-rail" aria-label="Workflow phase progression">
      {WORKFLOW_PHASE_ORDER.map((key, index) => {
        const state = index < activeIndex ? 'done' : index === activeIndex ? 'active' : 'pending'
        return (
          <div key={key} className={`workflow-phase-rail__chip workflow-phase-rail__chip--${state}`}>
            <span className="workflow-phase-rail__dot" aria-hidden />
            <span>{WORKFLOW_PHASE_LABELS[key]}</span>
          </div>
        )
      })}
      {phase.key === 'blocked' && (
        <div className="workflow-phase-rail__chip workflow-phase-rail__chip--blocked">
          <span className="workflow-phase-rail__dot" aria-hidden />
          <span>{phase.label}</span>
        </div>
      )}
    </div>
  )
}

const formatStepData = (data: Record<string, unknown> | undefined): string => {
  if (!data || Object.keys(data).length === 0) return '—'
  const body = workflowStepMarkdownBody(data)
  if (body) return body
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return '—'
  }
}

export const BatchProgressPanel: React.FC<{ progress?: WorkflowBatchProgress | null }> = ({ progress }) => {
  if (!progress || !progress.batch_mode) return null

  const total = Number(progress.total ?? 0)
  const completed = Number(progress.completed ?? 0)
  const failed = Number(progress.failed ?? 0)
  const preview = progress.items_preview?.length ? progress.items_preview.join(' · ') : ''

  return (
    <section className="batch-progress-panel">
      <div className="workflow-panel__header batch-progress-panel__header">
        <h3>Batch progress</h3>
        <span className="batch-progress-panel__meta">{progress.label || 'batch'}</span>
      </div>
      <div className="batch-progress-panel__metrics">
        <span><strong>{completed}</strong> completed</span>
        <span><strong>{failed}</strong> failed</span>
        <span><strong>{total}</strong> total</span>
      </div>
      {progress.current_item ? <p className="batch-progress-panel__current">Current: {progress.current_item}</p> : null}
      {preview ? <p className="batch-progress-panel__preview">Preview: {preview}</p> : null}
      {progress.status ? <p className="batch-progress-panel__status">Status: {progress.status}</p> : null}
    </section>
  )
}

export const StepCard: React.FC<{
  step: WorkflowStep
  index: number
  isActive: boolean
}> = ({ step, index, isActive }) => {
  const shouldAutoOpen = isActive || step.status === 'running' || step.status === 'failed'
  const [expanded, setExpanded] = useState(shouldAutoOpen)
  const badge = STEP_STATUS_LABELS[step.status] || step.status.toUpperCase()
  const agentText =
    step.agent_id ||
    (step.agent_ids && step.agent_ids.length > 0
      ? `Agents: ${step.agent_ids.join(', ')}`
      : 'Pending assignment')
  const note = getStepNote(step, isActive)
  const inputDetails = formatStepData(step.input_data)
  const outputDetails = formatStepData(step.output_data)
  const body = workflowStepMarkdownBody(step.output_data as Record<string, unknown>)
  const genUi = workflowStepGenUi(step.output_data as Record<string, unknown>)
  const artifacts = workflowStepArtifacts(step.output_data as Record<string, unknown>)
  const downloadArtifacts = async () => {
    if (artifacts.length === 0) return
    await downloadWorkspaceFiles(artifacts, `${step.step_id}-artifacts.zip`)
  }

  useEffect(() => {
    if (shouldAutoOpen) {
      setExpanded(true)
    }
  }, [shouldAutoOpen, step.step_id, step.status, isActive])

  return (
    <details
      className={`step-card ${step.status} ${isActive ? 'is-active' : ''}`}
      open={expanded}
      onToggle={(event) => setExpanded(event.currentTarget.open)}
    >
      <summary className="step-card__summary-toggle">
        <div className="step-card__summary-head">
          <div className="step-card__heading">
            <div className="step-card__heading-main">
              <span className="step-card__index">{index + 1}</span>
              <div className="step-card__heading-copy">
                <p className="step-card__name" title={step.name || step.step_id}>
                  {step.name || step.step_id}
                </p>
                <p className="step-card__mode">{step.execution_mode}</p>
              </div>
            </div>
            <span className="step-card__duration">
              {formatDuration(step.started_at, step.completed_at)}
            </span>
          </div>
          <span className="step-card__toggle-row">
            <span className="step-card__toggle-icon" aria-hidden />
            <span className="step-card__toggle-label">{expanded ? 'Collapse' : 'Expand'}</span>
          </span>
        </div>
        <div className="step-card__meta">
          <span className={`step-badge step-badge--${step.status}`}>{badge}</span>
          <span className="step-card__agent">{agentText}</span>
          {isActive && <span className="step-card__live">Live</span>}
        </div>
      </summary>
      <div className="step-card__content">
        {body && (
          <div className="step-card__body markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
          </div>
        )}
        {genUi && (
          <div className="step-card__protocol">
            <div className="step-card__protocol-label">Protocol output</div>
            <GenUiChart genUi={genUi as GenUiPayload} />
          </div>
        )}
        <p className="step-card__summary step-card__summary--state">{note}</p>
        <details className="step-card__artifacts" open>
          <summary>Artifacts</summary>
          <div className="step-card__artifact-grid">
            <section className="step-card__artifact-block">
              <h4>Input</h4>
              <pre className="step-card__artifact-json">{inputDetails}</pre>
            </section>
            <section className="step-card__artifact-block">
              <div className="step-card__artifact-block-header">
                <h4>Output</h4>
                {artifacts.length > 0 && (
                  <button type="button" className="step-card__artifact-download" onClick={downloadArtifacts}>
                    Download ({artifacts.length})
                  </button>
                )}
              </div>
              <pre className="step-card__artifact-json">{outputDetails}</pre>
            </section>
          </div>
        </details>
      </div>
    </details>
  )
}

export const TimelineEventCard: React.FC<{ event: TimelineEvent }> = ({ event }) => {
  return (
    <article className="timeline-event-card">
      <div className="timeline-event-card__header">
        <span className="timeline-event-card__label">{getEventLabel(event)}</span>
        <span className="timeline-event-card__time">{formatTimestamp(event.timestamp)}</span>
      </div>
      <p className="timeline-event-card__detail">{getEventDetail(event)}</p>
    </article>
  )
}

export const AgentCard: React.FC<{ agent: AgentState }> = ({ agent }) => {
  const hot = isRecentlyActive(agent.last_active) || agent.status === 'working'
  return (
    <article className={`agent-card ${hot ? 'agent-card--hot' : ''}`}>
      <div>
        <div className="agent-card__title-row">
          <span className={`agent-card__ring ${hot ? 'agent-card__ring--live' : ''}`} aria-hidden />
          <p className="agent-card__id">{agent.agent_id}</p>
        </div>
        <p className="agent-card__role">{agent.role}</p>
      </div>
      <div className="agent-card__meta">
        <span className={`agent-card__status agent-card__status--${hot ? 'live' : agent.status}`}>
          {agent.status}
        </span>
        <span className="agent-card__counts">
          {agent.task_count} tasks · {agent.message_count} msgs
        </span>
        <span className="agent-card__active">Last active {formatTimestamp(agent.last_active)}</span>
      </div>
    </article>
  )
}

export const FinalReportPanel: React.FC<{ report?: string; artifactFiles?: string[] }> = ({ report, artifactFiles = [] }) => {
  const [copied, setCopied] = useState(false)
  const downloadArtifacts = async () => {
    if (artifactFiles.length === 0) return
    await downloadWorkspaceFiles(artifactFiles, 'workflow-artifacts.zip')
  }

  if (!report) {
    return (
      <section className="final-report-panel final-report-panel--empty">
        <div className="final-report-panel__header">
          <h3>Final report</h3>
          {artifactFiles.length > 0 && (
            <button type="button" onClick={downloadArtifacts}>
              Download artifacts ({artifactFiles.length})
            </button>
          )}
        </div>
        <p>No summary generated yet. Awaiting final step output.</p>
      </section>
    )
  }

  const copyReport = async () => {
    await navigator.clipboard.writeText(report)
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }

  return (
    <section className="final-report-panel">
      <div className="final-report-panel__header">
        <h3>Final report</h3>
        <div className="final-report-panel__actions">
          {artifactFiles.length > 0 && (
            <button type="button" onClick={downloadArtifacts}>
              Download artifacts ({artifactFiles.length})
            </button>
          )}
          <button type="button" onClick={copyReport}>
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>
      <div className="final-report-panel__body markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
      </div>
    </section>
  )
}

interface SteeringPanelProps {
  isRunning: boolean
  steeringLog: SteeringNote[]
  onSteeringSubmit?: (text: string) => void
}

export const SteeringPanel: React.FC<SteeringPanelProps> = ({
  isRunning,
  steeringLog,
  onSteeringSubmit,
}) => {
  const [draft, setDraft] = useState('')
  const submit = () => {
    const text = draft.trim()
    if (!text || !onSteeringSubmit) return
    onSteeringSubmit(text)
    setDraft('')
  }

  if (!onSteeringSubmit || !isRunning) return null

  return (
    <div className="workflow-steering">
      <h3 className="workflow-steering-title">Steering</h3>
      <p className="workflow-steering-hint">
        Share short guidance with the agents (Cmd+Enter to send).
      </p>
      <div className="workflow-steering-row">
        <textarea
          className="workflow-steering-input"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder="e.g. Prioritize accuracy over creativity."
        />
        <button className="workflow-steering-send" type="button" onClick={submit}>
          Send
        </button>
      </div>
      {steeringLog.length > 0 && (
        <ul className="workflow-steering-log">
          {steeringLog.map((note) => (
            <li key={note.id}>
              <time dateTime={note.at}>{new Date(note.at).toLocaleTimeString()}</time>
              <span>{note.text}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

interface DebugWorkflowDetailsProps {
  timeline: TimelineEvent[]
  agents: AgentState[]
}

export const DebugWorkflowDetails: React.FC<DebugWorkflowDetailsProps> = ({ timeline, agents }) => {
  if (timeline.length === 0 && agents.length === 0) return null

  return (
    <details className="workflow-debug-panel">
      <summary>Debug details</summary>
      {agents.length > 0 && (
        <section className="workflow-debug-panel__section">
          <h4>Agents</h4>
          <div className="agent-grid">
            {agents.map((agent) => (
              <AgentCard key={agent.agent_id} agent={agent} />
            ))}
          </div>
        </section>
      )}
      {timeline.length > 0 && (
        <section className="workflow-debug-panel__section">
          <h4>Timeline</h4>
          <div className="timeline-list">
            {timeline.map((event) => (
              <TimelineEventCard key={event.event_id} event={event} />
            ))}
          </div>
        </section>
      )}
    </details>
  )
}
