/**
 * InputArea - text input, skill/file dropdowns, send mode, send button.
 */

import type { Skill } from '../../types'

interface InputAreaProps {
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
  lastCancelledRunId?: string | null
  onKeyDown: (e: React.KeyboardEvent) => void
  inputRef: React.RefObject<HTMLInputElement | null>
}

const FILE_FILTER_LIMIT = 20

export function InputArea({
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
  onSend,
  onCancel,
  onResume,
  lastCancelledRunId,
  runId,
  onKeyDown,
  inputRef,
}: InputAreaProps) {
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

  return (
    <div className="input-area">
      <div className="input-wrap">
        {showSkillDropdown && (
          <div className="dropdown skill-dropdown">
            <div className="dropdown-title">Select skill</div>
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
            <div className="dropdown-title">Select file (@ path)</div>
            <input
              type="text"
              placeholder="Filter..."
              value={fileQuery}
              onChange={(e) => setFileQuery(e.target.value)}
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
        {selectedSkill && (
          <span className="skill-badge">{selectedSkill.name}</span>
        )}
        <input
          ref={inputRef}
          type="text"
          placeholder={
            selectedSkill
              ? selectedSkill.description
              : 'Ask anything · / select skill · @ select file'
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => setInput((i) => i)}
          disabled={(!allowBackground || sendMode === 'sync') && loading}
        />
        {allowBackground && (
          <span
            className="send-mode-toggle"
            title={
              sendMode === 'async'
                ? 'Send in background (input never blocked)'
                : 'Wait for reply in this chat'
            }
          >
            <button
              type="button"
              className={sendMode === 'async' ? 'active' : ''}
              onClick={() => setSendMode('async')}
            >
              Background
            </button>
            <button
              type="button"
              className={sendMode === 'sync' ? 'active' : ''}
              onClick={() => setSendMode('sync')}
            >
              Wait
            </button>
          </span>
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
        ) : (
          <button
            type="button"
            className="btn-send"
            onClick={onSend}
            disabled={(!allowBackground || sendMode === 'sync') && loading}
          >
            Send
          </button>
        )}
      </div>
    </div>
  )
}
