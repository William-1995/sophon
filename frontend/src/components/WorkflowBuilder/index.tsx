import React, { useCallback, useId, useMemo, useRef, useState } from 'react'
import { useComposerVoice } from '../../hooks/useComposerVoice'
import { AttachmentChips } from '../composer/AttachmentChips'
import { VoiceCaption } from '../composer/VoiceCaption'
import { composePlaceholder, createAttachmentId, createStableInputId } from '../composer/composerUtils'

interface FileAttachment {
  file: File
  id: string
}

interface WorkflowBuilderProps {
  onSubmit: (text: string, attachments: File[]) => void | Promise<void>
  isLoading?: boolean
  workspaceFiles?: string[]
  stageLabel?: string | null
  stageHint?: string | null
  allowEditingWhileBusy?: boolean
}

const FILE_FILTER_LIMIT = 20

function stageTone(stageLabel?: string | null): string | null {
  const value = String(stageLabel ?? '').toLowerCase()
  if (value.includes('investig')) return 'Investigating'
  if (value.includes('clarif')) return 'Clarifying'
  if (value.includes('plan')) return 'Planning'
  if (value.includes('execut')) return 'Executing'
  if (value.includes('wait')) return 'Waiting'
  return null
}

export function WorkflowBuilder({
  onSubmit,
  isLoading = false,
  workspaceFiles = [],
  stageLabel = null,
  stageHint = null,
  allowEditingWhileBusy = true,
}: WorkflowBuilderProps) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<FileAttachment[]>([])
  const [showFileDropdown, setShowFileDropdown] = useState(false)
  const [fileQuery, setFileQuery] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { recording, transcribing, liveTranscript, voiceCapable, toggleRecord } =
    useComposerVoice(setText)
  const rawId = useId()
  const fileInputId = createStableInputId('workflow-attach', rawId)

  const filteredFiles = useMemo(() => {
    const query = fileQuery.trim().toLowerCase()
    return query
      ? workspaceFiles.filter((f) => f.toLowerCase().includes(query))
      : workspaceFiles
  }, [workspaceFiles, fileQuery])

  const uploadDisabled = isLoading && !allowEditingWhileBusy

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return
    const newFiles = Array.from(files).map((file) => ({ file, id: createAttachmentId() }))
    setAttachments((prev) => [...prev, ...newFiles])
  }, [])

  const handleRemoveAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((att) => att.id !== id))
  }, [])

  const insertWorkspaceFile = useCallback((path: string) => {
    setText((prev) => {
      const suffix = prev && !prev.endsWith(' ') ? ' ' : ''
      return `${prev}${suffix}@${path}`
    })
    setShowFileDropdown(false)
    setFileQuery('')
    textareaRef.current?.focus()
  }, [])

  const handleSubmit = useCallback(async () => {
    const trimmed = text.trim()
    if (!trimmed && attachments.length === 0) return
    if (isLoading) return
    await onSubmit(text, attachments.map((att) => att.file))
    setText('')
    setAttachments([])
    setShowFileDropdown(false)
    setFileQuery('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [attachments, isLoading, onSubmit, text])

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSubmit()
      return
    }
    if (e.key === '@') {
      const el = e.currentTarget
      const pos = el.selectionStart ?? el.value.length
      const before = el.value.slice(0, pos)
      if (before.length === 0 || /[\s\n]$/.test(before)) {
        e.preventDefault()
        setShowFileDropdown((prev) => !prev)
        setFileQuery('')
      }
    }
    if (e.key === 'Escape') {
      setShowFileDropdown(false)
    }
  }

  const onChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    const target = e.target
    target.style.height = 'auto'
    target.style.height = `${Math.min(target.scrollHeight, 220)}px`
  }

  return (
    <div className="input-area workflow-composer">
      <div className="chat-content-max input-area__column workflow-composer__inner">
        <VoiceCaption text={(recording || transcribing) ? liveTranscript : null} />
        <div className="workflow-composer__main">
          {stageTone(stageLabel) && (
            <div className="workflow-composer__stage">
              <span className="workflow-composer__stage-label">{stageTone(stageLabel)}</span>
              {stageHint && <span id="workflow-stage-hint" className="workflow-composer__stage-hint">{stageHint}</span>}
            </div>
          )}

          <AttachmentChips
            title="Pending attachments"
            ariaLabel="Workflow context"
            items={attachments.map((att) => ({
              id: att.id,
              name: att.file.name,
              onRemove: () => handleRemoveAttachment(att.id),
              disabled: isLoading,
            }))}
          />
          <div className="input-wrap input-wrap--multiline workflow-composer__input-wrap">
            <div className="input-wrap__leading workflow-composer__leading" aria-label="Attach files">
              <input
                id={fileInputId}
                type="file"
                multiple
                className="file-input-workspace"
                tabIndex={-1}
                onChange={(e) => handleFileSelect(e.target.files)}
                disabled={uploadDisabled}
              />
              <label
                htmlFor={uploadDisabled ? undefined : fileInputId}
                className={`btn-upload hover-tip hover-tip--right${uploadDisabled ? ' btn-upload-disabled' : ''}`}
                data-tooltip="Upload local files. They are sent with your workflow request."
                aria-label="Attach files"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  width="20"
                  height="20"
                  aria-hidden
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </label>

              <button
                type="button"
                className={`composer-hint-btn hover-tip hover-tip--right${showFileDropdown ? ' composer-hint-btn--active' : ''}`}
                onClick={() => {
                  setShowFileDropdown((prev) => !prev)
                  setFileQuery('')
                }}
                aria-label="Insert workspace file path"
                aria-expanded={showFileDropdown}
                aria-haspopup="listbox"
                data-tooltip="Insert a workspace file path. Type @ or click here."
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  width="20"
                  height="20"
                  aria-hidden
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <path d="M9 13h6M9 17h6M9 9h4" />
                </svg>
              </button>
            </div>

            <div className="input-wrap__field workflow-composer__field">
              <textarea
                ref={textareaRef}
                className="chat-input-field workflow-composer__textarea"
                value={text}
                onChange={onChange}
                onKeyDown={onKeyDown}
                placeholder={composePlaceholder('Describe your workflow goal')}
                disabled={false}
                rows={1}
                aria-describedby={stageHint ? 'workflow-stage-hint' : undefined}
              />
              <div className="workflow-composer__helper">
                Use @ for files · Enter to send
              </div>
            </div>

            <div className="input-wrap__trailing workflow-composer__actions" aria-label="Voice input">
              <button
                type="button"
                className={`btn-mic ${recording ? 'recording' : ''} ${!voiceCapable && !recording ? 'btn-mic--unavailable' : ''}`}
                onClick={() => void toggleRecord()}
                disabled={transcribing || (!voiceCapable && !recording)}
                title={
                  recording
                    ? 'Stop recording'
                    : transcribing
                      ? 'Transcribing…'
                      : !voiceCapable
                        ? 'Voice unavailable in this browser: use Chrome or Edge for live dictation, or enable speech-to-text on the server'
                        : 'Voice input — click to speak; text is added to the message'
                }
                aria-label={
                  !voiceCapable && !recording
                    ? 'Voice input (not available in this environment)'
                    : recording
                      ? 'Stop recording'
                      : 'Voice input'
                }
              >
                {recording ? (
                  <span className="btn-mic-waves" aria-hidden>
                    <svg viewBox="0 0 24 24" fill="currentColor">
                      <rect x="6" y="8" width="2" height="8" rx="1" className="bar bar-1" />
                      <rect x="11" y="4" width="2" height="16" rx="1" className="bar bar-2" />
                      <rect x="16" y="8" width="2" height="8" rx="1" className="bar bar-3" />
                    </svg>
                  </span>
                ) : (
                  <span className="btn-mic-icon" aria-hidden>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z" />
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                      <line x1="12" y1="19" x2="12" y2="22" />
                    </svg>
                  </span>
                )}
              </button>
            </div>
          </div>

          {showFileDropdown && (
            <div className="dropdown file-dropdown workflow-file-dropdown">
              <div className="dropdown-head">
                <span className="dropdown-title">Select workspace file</span>
                <button
                  type="button"
                  className="dropdown-close"
                  onClick={() => setShowFileDropdown(false)}
                  aria-label="Close file menu"
                >
                  ×
                </button>
              </div>
              <input
                type="text"
                placeholder="Filter..."
                value={fileQuery}
                onChange={(e) => setFileQuery(e.target.value)}
                autoFocus
              />
              <div className="dropdown-options">
                {filteredFiles.slice(0, FILE_FILTER_LIMIT).map((f) => (
                  <button key={f} type="button" onClick={() => insertWorkspaceFile(f)}>
                    {f}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
