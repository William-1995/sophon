/**
 * ChatArea - session bar, message list, scroll-to-bottom, input.
 */

import { MessageList } from '../MessageList/MessageList'
import { InputArea } from '../InputArea/InputArea'
import { formatSessionId } from '../../utils/session'
import type { Message as MessageType, Skill } from '../../types'
import type { LiveTodo } from '../../hooks/useChat'

export interface LiveEvent {
  type: string
  [key: string]: unknown
}

interface ChatAreaProps {
  latestEmotion?: string | null
  currentSessionId: string | null
  allowBackground?: boolean
  messages: MessageType[]
  loading: boolean
  sessionStatus: string | null
  liveTokens: number | null
  liveEvents?: LiveEvent[]
  liveTodos?: { id: string; title: string; status: string }[]
  liveTodos?: LiveTodo[]
  chatContainerRef: React.RefObject<HTMLDivElement | null>
  chatEndRef: React.RefObject<HTMLDivElement | null>
  showScrollToBottom: boolean
  onChatScroll: () => void
  onScrollToBottom: () => void
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
  onSend: () => void
  onCancel?: () => void
  onResume?: () => void
  lastCancelledRunId?: string | null
  runId?: string | null
  onKeyDown: (e: React.KeyboardEvent) => void
  inputRef: React.RefObject<HTMLInputElement | null>
}

export function ChatArea({
  latestEmotion,
  currentSessionId,
  allowBackground = true,
  messages,
  loading,
  sessionStatus,
  liveTokens,
  liveEvents = [],
  liveTodos = [],
  chatContainerRef,
  chatEndRef,
  showScrollToBottom,
  onChatScroll,
  onScrollToBottom,
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
  onSend,
  onCancel,
  onResume,
  lastCancelledRunId,
  runId,
  onKeyDown,
  inputRef,
}: ChatAreaProps) {
  return (
    <div className="chat-area">
      <div className="chat-session-bar">
        <span className="session-id-label">Session</span>
        <code className="session-id-value">
          {formatSessionId(currentSessionId)}
        </code>
      </div>
      <div
        className="chat-container"
        ref={chatContainerRef}
        onScroll={onChatScroll}
      >
        <MessageList
          messages={messages}
          loading={loading}
          sessionStatus={sessionStatus}
          liveTokens={liveTokens}
          liveEvents={liveEvents}
          liveTodos={liveTodos}
          chatEndRef={chatEndRef}
        />
      </div>
      {showScrollToBottom && (
        <button
          type="button"
          className="btn-scroll-to-bottom"
          onClick={onScrollToBottom}
          aria-label="Scroll to bottom"
        >
          ↓
        </button>
      )}
      <InputArea
        latestEmotion={latestEmotion}
        input={input}
        setInput={setInput}
        selectedSkill={selectedSkill}
        setSelectedSkill={setSelectedSkill}
        skills={skills}
        workspaceFiles={workspaceFiles}
        showSkillDropdown={showSkillDropdown}
        setShowSkillDropdown={setShowSkillDropdown}
        showFileDropdown={showFileDropdown}
        setShowFileDropdown={setShowFileDropdown}
        fileQuery={fileQuery}
        setFileQuery={setFileQuery}
        sendMode={sendMode}
        setSendMode={setSendMode}
        allowBackground={allowBackground}
        loading={loading}
        onSend={onSend}
        onCancel={onCancel}
        onResume={onResume}
        lastCancelledRunId={lastCancelledRunId}
        runId={runId}
        onKeyDown={onKeyDown}
        inputRef={inputRef}
      />
    </div>
  )
}
