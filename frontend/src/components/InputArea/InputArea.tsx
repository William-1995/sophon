/**
 * InputArea — multiline composer; / and @ open skill/file pickers; send mode, attach + voice.
 * Enter sends, Shift+Enter newline. Web Speech when available; emotion-colored mic pulse.
 */

import { useEffect, useRef, useId } from 'react'
import { EMOTION_RING_COLORS, EMOTION_RING_DEFAULT } from '../../constants'
import { useComposerVoice } from '../../hooks/useComposerVoice'
import type { Skill } from '../../types'
import { AttachmentChips } from '../composer/AttachmentChips'
import { VoiceCaption } from '../composer/VoiceCaption'
import { composePlaceholder, createStableInputId } from '../composer/composerUtils'

interface InputAreaProps {
  latestEmotion?: string | null
  input: string
  setInput: React.Dispatch<React.SetStateAction<string>>
  selectedSkill: Skill | null
  setSelectedSkill: React.Dispatch<React.SetStateAction<Skill | null>>
  skills: Skill[]
  workspaceFiles: string[]
  showSkillDropdown: boolean
  setShowSkillDropdown: React.Dispatch<React.SetStateAction<boolean>>
  showFileDropdown: boolean
  setShowFileDropdown: React.Dispatch<React.SetStateAction<boolean>>
  fileQuery: string
  setFileQuery: React.Dispatch<React.SetStateAction<string>>
  sendMode: 'async' | 'sync'
  setSendMode: React.Dispatch<React.SetStateAction<'async' | 'sync'>>
  allowBackground?: boolean
  loading: boolean
  runId?: string | null
  onSend: () => void
  onCancel?: () => void
  onResume?: () => void
  onNewSession?: () => void
  lastCancelledRunId?: string | null
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
  inputRef: React.RefObject<HTMLTextAreaElement | null>
  /** Add files from picker; they upload when message is sent (Enter). */
  onAddPendingWorkspaceFiles?: (files: File[]) => void
  attachmentUploading?: boolean
  /** Enables Send when input is empty but files are pending */
  pendingAttachmentCount?: number
  /** Filenames to show above the input (must stay next to the text field). */
  pendingAttachmentNames?: string[]
  onRemovePendingWorkspaceFile?: (index: number) => void
  attachmentHint?: string | null
}

const FILE_FILTER_LIMIT = 20

export function InputArea({
  latestEmotion,
  input,
  setInput,
  selectedSkill,
  setSelectedSkill,
  skills,
  workspaceFiles,
  showSkillDropdown,
  setShowSkillDropdown,
  showFileDropdown,
  setShowFileDropdown,
  fileQuery,
  setFileQuery,
  sendMode,
  setSendMode,
  allowBackground = true,
  loading,
  onSend: _onSend,
  onCancel,
  onResume,
  onNewSession,
  lastCancelledRunId,
  runId,
  onKeyDown,
  inputRef,
  onAddPendingWorkspaceFiles,
  attachmentUploading = false,
  pendingAttachmentCount: _pendingAttachmentCount = 0,
  pendingAttachmentNames = [],
  onRemovePendingWorkspaceFile,
  attachmentHint = null,
}: InputAreaProps) {
  const { recording, transcribing, liveTranscript, voiceCapable, toggleRecord } =
    useComposerVoice(setInput)
  /** Stable id without colons (valid htmlFor / querySelector on all engines). */
  const workspaceFileInputId = createStableInputId('ws-attach', useId())
  const composerShellRef = useRef<HTMLDivElement>(null)

  /** Keep textarea focused while skill menu is open so `/` can toggle close from the same handler. */
  useEffect(() => {
    if (!showSkillDropdown) return
    const id = window.requestAnimationFrame(() => {
      inputRef.current?.focus()
    })
    return () => window.cancelAnimationFrame(id)
  }, [showSkillDropdown])

  useEffect(() => {
    if (!showSkillDropdown && !showFileDropdown) return
    const onPointerDown = (ev: PointerEvent) => {
      const root = composerShellRef.current
      if (root && !root.contains(ev.target as Node)) {
        setShowSkillDropdown(false)
        setShowFileDropdown(false)
      }
    }
    document.addEventListener('pointerdown', onPointerDown, true)
    return () => document.removeEventListener('pointerdown', onPointerDown, true)
  }, [showSkillDropdown, showFileDropdown, setShowSkillDropdown, setShowFileDropdown])

  const getPulseColor = () => {
    if (!latestEmotion) return undefined
    const c = EMOTION_RING_COLORS[latestEmotion.toLowerCase()]
    return c ?? (latestEmotion ? EMOTION_RING_DEFAULT : undefined)
  }

  const filteredFiles = fileQuery
    ? workspaceFiles.filter((f) =>
        f.toLowerCase().includes(fileQuery.toLowerCase())
      )
    : workspaceFiles

  const selectSkill = (skill: Skill | null) => {
    setSelectedSkill(skill)
    setShowSkillDropdown(false)
    inputRef.current?.focus()
  }

  const selectFile = (path: string) => {
    setInput((i) => i + (i ? ' ' : '') + `@${path}`)
    setShowFileDropdown(false)
    inputRef.current?.focus()
  }

  const onWorkspaceFilesPicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const el = e.target
    const list = el.files
    const files = list?.length ? Array.from(list) : []
    el.value = ''
    if (files.length === 0 || !onAddPendingWorkspaceFiles) return
    onAddPendingWorkspaceFiles(files)
  }

  const pulseColor = getPulseColor()
  const workspaceUploadDisabled =
    attachmentUploading || ((!allowBackground || sendMode === 'sync') && loading)

  const inputPlaceholder = (() => {
    if (selectedSkill) return selectedSkill.description
    if (pendingAttachmentNames.length > 0) {
      const shown = pendingAttachmentNames.slice(0, 4).join(', ')
      const extra =
        pendingAttachmentNames.length > 4
          ? ` +${pendingAttachmentNames.length - 4}`
          : ''
      return `${pendingAttachmentNames.length} file(s) selected: ${shown}${extra} · Send to upload to workspace`
    }
    return composePlaceholder('Message · / skills · @ files')
  })()

  const openSkillPicker = () => {
    if (showSkillDropdown) {
      setShowSkillDropdown(false)
    } else {
      setShowSkillDropdown(true)
      setShowFileDropdown(false)
      setFileQuery('')
    }
    inputRef.current?.focus()
  }

  const openFilePicker = () => {
    if (showFileDropdown) {
      setShowFileDropdown(false)
    } else {
      setShowFileDropdown(true)
      setShowSkillDropdown(false)
      setFileQuery('')
    }
    inputRef.current?.focus()
  }

  return (
    <div className="input-area" ref={composerShellRef}>
      <div className="chat-content-max input-area__column">
      <VoiceCaption text={(recording || transcribing) ? liveTranscript : null} />
      <AttachmentChips
        items={pendingAttachmentNames.map((name, i) => ({
          id: `${name}-${i}`,
          name,
          onRemove: onRemovePendingWorkspaceFile ? () => onRemovePendingWorkspaceFile(i) : undefined,
        }))}
      />
      {attachmentHint && (
        <div className="attachment-hint" role="status">
          {attachmentHint}
        </div>
      )}
      <div className="input-wrap input-wrap--multiline">
        {showSkillDropdown && (
          <div className="dropdown skill-dropdown">
            <div className="dropdown-head">
              <span className="dropdown-title">Select skill</span>
              <button
                type="button"
                className="dropdown-close"
                onClick={() => setShowSkillDropdown(false)}
                aria-label="Close skill menu"
              >
                ×
              </button>
            </div>
            <div className="dropdown-options">
              <button onClick={() => selectSkill(null)}>auto</button>
              {skills.map((s) => (
                <button key={s.name} onClick={() => selectSkill(s)}>
                  {s.name}
                </button>
              ))}
            </div>
          </div>
        )}
        {showFileDropdown && (
          <div className="dropdown file-dropdown">
            <div className="dropdown-head">
              <span className="dropdown-title">Select file (@ path)</span>
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
              data-composer-file-filter
              autoFocus
            />
            <div className="dropdown-options">
              {filteredFiles.slice(0, FILE_FILTER_LIMIT).map((f) => (
                <button key={f} onClick={() => selectFile(f)}>
                  {f}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="input-wrap__leading" aria-label="Attach, skills, and files">
          {onAddPendingWorkspaceFiles && (
            <>
              <input
                id={workspaceFileInputId}
                type="file"
                multiple
                className="file-input-workspace"
                tabIndex={-1}
                onChange={onWorkspaceFilesPicked}
                disabled={workspaceUploadDisabled}
              />
              <label
                htmlFor={workspaceUploadDisabled ? undefined : workspaceFileInputId}
                className={`btn-upload hover-tip hover-tip--right${workspaceUploadDisabled ? ' btn-upload-disabled' : ''}`}
                data-tooltip="Upload files to your workspace. They are stored when you send the message."
                aria-label="Attach files"
              >
                {attachmentUploading ? (
                  <span className="btn-upload-spinner" aria-hidden />
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20" aria-hidden>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                )}
              </label>
            </>
          )}
          <div className="composer-hint-group" role="group" aria-label="Skills and workspace file paths">
            <button
              type="button"
              className={`composer-hint-btn hover-tip hover-tip--right${showSkillDropdown ? ' composer-hint-btn--active' : ''}`}
              onClick={openSkillPicker}
              aria-label="Skills"
              aria-expanded={showSkillDropdown}
              aria-haspopup="listbox"
              data-tooltip="Skills — choose how the assistant runs, or type / on a new line. Press Esc or click outside to close."
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden>
                <rect x="2" y="4" width="14" height="5" rx="1" />
                <rect x="5" y="10" width="14" height="5" rx="1" />
                <rect x="8" y="16" width="14" height="5" rx="1" />
              </svg>
            </button>
            <button
              type="button"
              className={`composer-hint-btn hover-tip hover-tip--right${showFileDropdown ? ' composer-hint-btn--active' : ''}`}
              onClick={openFilePicker}
              aria-label="Workspace file path"
              aria-expanded={showFileDropdown}
              aria-haspopup="listbox"
              data-tooltip="Insert a workspace file path — type @ after a space or at the start of a line, or click here. Esc or outside click closes the list."
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <path d="M9 13h6M9 17h6M9 9h4" />
              </svg>
            </button>
          </div>
        </div>

        <div className="input-wrap__field">
          {selectedSkill && (
            <span className="skill-badge">{selectedSkill.name}</span>
          )}
          <textarea
            ref={inputRef}
            className="chat-input-field"
            rows={1}
            placeholder={inputPlaceholder}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            onFocus={() => setInput((i) => i)}
            disabled={(!allowBackground || sendMode === 'sync') && loading}
            aria-describedby={
              pendingAttachmentNames.length > 0 ? 'input-pending-desc' : undefined
            }
          />
          {pendingAttachmentNames.length > 0 && (
            <span id="input-pending-desc" className="sr-only">
              {pendingAttachmentNames.length} file(s) pending send:{' '}
              {pendingAttachmentNames.join(', ')}
            </span>
          )}
        </div>

        <div className="input-wrap__trailing" aria-label="Send mode and voice">
          {allowBackground && (
            <div className="send-mode-segmented" role="group" aria-label="Send mode — how replies are delivered (not Skills or @ files)">
              <button
                type="button"
                className={`hover-tip hover-tip--left ${sendMode === 'async' ? 'active' : ''}`}
                onClick={() => setSendMode('async')}
                aria-label="Background send mode"
                aria-pressed={sendMode === 'async'}
                title="Background"
                data-tooltip="In time — reply streams while you keep typing"
              >
                <span className="send-mode-icon send-mode-icon--async" aria-hidden>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="10" cy="12" r="5.5" />
                    <path d="M10 8.4v3.8l2.8 1.6" />
                    <path d="M14.5 9.5h4.5" />
                    <path d="M16.2 7.8l2.8 1.7-2.8 1.7" />
                  </svg>
                </span>
              </button>
              <button
                type="button"
                className={`hover-tip hover-tip--left ${sendMode === 'sync' ? 'active' : ''}`}
                onClick={() => setSendMode('sync')}
                aria-label="Wait for reply mode"
                aria-pressed={sendMode === 'sync'}
                title="Wait"
                data-tooltip="Out of time — pause input until this reply ends"
              >
                <span className="send-mode-icon send-mode-icon--sync" aria-hidden>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="8.5" />
                    <path d="M12 7.5v4.25" />
                    <path d="M12 12h3.5" />
                    <path d="M9 12.2v3.5" />
                    <path d="M9.5 15.6h5" />
                  </svg>
                </span>
              </button>
            </div>
          )}
          {loading && runId && sendMode === 'sync' && onCancel ? (
            <button
              type="button"
              className="btn-cancel"
              onClick={onCancel}
              title="Cancel run"
            >
              Cancel
            </button>
          ) : lastCancelledRunId && !loading && onResume ? (
            <button
              type="button"
              className="btn-resume"
              onClick={onResume}
              title="Resume from checkpoint"
            >
              Resume
            </button>
          ) : null}
          <button
            type="button"
            className={`btn-mic ${recording ? 'recording' : ''} ${pulseColor ? 'btn-mic-emotion' : ''} ${!voiceCapable && !recording ? 'btn-mic--unavailable' : ''}`}
            style={
              pulseColor && recording
                ? ({ '--mic-pulse-color': pulseColor } as React.CSSProperties)
                : undefined
            }
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
      </div>
    </div>
  )
}
