import { useState, useEffect } from 'react'
import { WorkflowHistory } from '../WorkflowHistory'
import { WorkflowBuilder } from '../WorkflowBuilder'
import { StatusMonitor, type SteeringNote } from '../StatusMonitor'
import { useWorkflow, useSSE } from '../../hooks'
import { getWorkflowInstance } from '../../api/cowork'
import { uploadWorkspaceFiles } from '../../api/resources'
import {
  createWorkflowFromText,
  executeWorkflow,
} from '../../api/workflow'
import { mergeWorkflowState } from '../../utils/mergeWorkflowState'
import type { WorkflowState } from '../../types/cowork'
import { describeWorkflowStage } from '../workflow/workflowView'

interface CoworkPanelProps {
  isOpen: boolean
  onClose: () => void
  workspaceFiles: string[]
  onRefreshWorkspaceFiles: () => Promise<void>
}


export function CoworkPanel({
  isOpen,
  onClose,
  workspaceFiles,
  onRefreshWorkspaceFiles,
}: CoworkPanelProps) {
  const [mode, setMode] = useState<'history' | 'monitor'>('history')
  const [isCreating, setIsCreating] = useState(false)
  const [pendingGoal, setPendingGoal] = useState<string | null>(null)
  const [steeringLog, setSteeringLog] = useState<SteeringNote[]>([])
  const { workflowState, pause, resume, stop, setWorkflowState } = useWorkflow()

  const isWorkflowActive =
    workflowState?.status &&
    workflowState.status !== 'completed' &&
    workflowState.status !== 'failed'

  useSSE(isWorkflowActive ? workflowState?.instance_id || null : null, {
    onMessage: (data) => {
      setWorkflowState((prev) => mergeWorkflowState(prev, data))
      if (data.status === 'running' || data.status === 'queued') {
        setMode('monitor')
      }
    },
  })

  useEffect(() => {
    setSteeringLog([])
  }, [workflowState?.instance_id])

  if (!isOpen) return null

  const handleCreateWorkflow = async (text: string, attachments: File[] = []) => {
    const trimmed = text.trim()
    if (!trimmed && attachments.length === 0) return
    setIsCreating(true)
    setPendingGoal(trimmed || 'Analyze the attached files')
    setMode('monitor')
    setWorkflowState(null)
    try {
      let finalText = trimmed
    let uploadedFiles: string[] = []
      if (attachments.length > 0) {
        const upload = await uploadWorkspaceFiles(attachments, 'docs')
        await onRefreshWorkspaceFiles()
        uploadedFiles = upload.saved
        const refs = upload.saved.map((p) => `@${p}`).join(' ')
        finalText = [finalText, refs].filter(Boolean).join(' ').trim()
        if (!finalText) {
          finalText = `Analyze these files: ${refs || 'attached documents'}`
        }
      }

      const result = await createWorkflowFromText(finalText, uploadedFiles)
      await executeWorkflow(result.instance_id)
      const stateRes = await getWorkflowInstance(result.instance_id)
      if (stateRes.data) {
        setWorkflowState(stateRes.data)
      }
      setMode('monitor')
    } catch (error) {
      console.error('Failed to create workflow:', error)
      alert('Failed to create workflow: ' + (error as Error).message)
    } finally {
      setIsCreating(false)
      setPendingGoal(null)
    }
  }

  const stage = describeWorkflowStage(workflowState, isCreating, pendingGoal)
  const showStageBanner = mode === 'history' && Boolean(stage.label && stage.label !== 'Ready')
  const showComposer = mode === 'history'

  return (
    <div className="chat-area">
      <div className="chat-session-bar">
        <div className="chat-content-max chat-session-bar__inner">
          <div className="workflow-bar__leading">
            <span className="session-id-label">Workflow</span>
            <div
              className="header-tabs workflow-bar__tabs"
              role="tablist"
              aria-label="Workflow view"
            >
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'history'}
                className={mode === 'history' ? 'active' : ''}
                onClick={() => setMode('history')}
              >
                Recent
              </button>
              {workflowState && (
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'monitor'}
                  className={mode === 'monitor' ? 'active' : ''}
                  onClick={() => setMode('monitor')}
                >
                  Monitor
                </button>
              )}
            </div>
          </div>
          <button
            type="button"
            className="cowork-panel__close"
            onClick={onClose}
            aria-label="Close workflow"
          >
            ×
          </button>
        </div>
      </div>

      <div className="chat-container">
        <div className="chat-content-max">
          {showStageBanner && (
            <div className="workflow-stage-banner">
              <span className="workflow-stage-banner__label">{stage.label}</span>
              {stage.hint ? <span className="workflow-stage-banner__hint">{stage.hint}</span> : null}
            </div>
          )}
          <div className="chat workflow-chat-scroll">
            {mode === 'history' && (
              <WorkflowHistory
                onSelectInstance={async (instanceId: string) => {
                  const result = await getWorkflowInstance(instanceId)
                  if (result.data) {
                    setWorkflowState(result.data)
                    setMode('monitor')
                  } else if (result.error) {
                    alert(result.error)
                  }
                }}
              />
            )}

            {mode === 'monitor' &&
              (workflowState ? (
                <StatusMonitor
                  workflowState={workflowState}
                  onPause={pause}
                  onResume={resume}
                  onStop={stop}
                  steeringLog={steeringLog}
                  onSteeringSubmit={(text) =>
                    setSteeringLog((prev) => [
                      ...prev,
                      {
                        id: `${Date.now()}-${prev.length}`,
                        text,
                        at: new Date().toISOString(),
                      },
                    ])
                  }
                />
              ) : (
                <div className="workflow-empty">
                  <p className="workflow-empty__title">Starting your workflow</p>
                  <p className="workflow-empty__hint">
                    Send a goal in the composer below and we'll begin investigating, planning, and executing it here.
                  </p>
                </div>
              ))}
          </div>
        </div>
      </div>

      {showComposer && (
        <WorkflowBuilder
          onSubmit={handleCreateWorkflow}
          isLoading={isCreating}
          workspaceFiles={workspaceFiles}
          stageLabel={stage.label}
          stageHint={stage.hint}
        />
      )}
    </div>
  )
}
