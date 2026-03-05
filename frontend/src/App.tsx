/**
 * App - composition root. Orchestrates hooks and components.
 * Clean separation: hooks handle state/logic, components handle UI.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useSessions } from './hooks/useSessions'
import { useChat } from './hooks/useChat'
import { useOrbPanel } from './hooks/useOrbPanel'
import { useEventSource } from './hooks/useEventSource'
import { useNotifications } from './hooks/useNotifications'
import { ChatArea } from './components/ChatArea/ChatArea'
import { OrbPanel } from './components/OrbPanel/OrbPanel'
import { fetchSkills, fetchWorkspaceFiles } from './api/resources'
import { ORB_RESIZE_MIN } from './constants'
import './App.css'

function App() {
  const [skills, setSkills] = useState<{ name: string; description: string }[]>([])
  const [workspaceFiles, setWorkspaceFiles] = useState<string[]>([])
  const [showSkillDropdown, setShowSkillDropdown] = useState(false)
  const [showFileDropdown, setShowFileDropdown] = useState(false)
  const [fileQuery, setFileQuery] = useState('')
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)

  const chatContainerRef = useRef<HTMLDivElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const inputDraftsRef = useRef<Record<string, string>>({})

  const sessions = useSessions()
  const {
    currentSessionId,
    setCurrentSessionId,
    messages,
    setMessages,
    sessionStatus,
    fetchSessions,
    fetchSessionTree,
    switchToSession: switchToSessionBase,
    handleNewSession,
    handleDeleteSession,
    handleForkSession,
    refreshRefs,
  } = sessions

  const chat = useChat({
    currentSessionId,
    setCurrentSessionId,
    messages,
    setMessages,
    fetchSessions,
    setWorkspaceFiles,
    inputDraftsRef,
  })

  const orbPanel = useOrbPanel({
    treeRoots: sessions.treeRoots,
    skills,
    workspaceFiles,
  })

  useEventSource({
    onRefreshTree: () => refreshRefs.fetchSessionTree.current?.(),
    onRefreshSessions: () => refreshRefs.fetchSessions.current?.(),
    onRefreshMessages: (id) => refreshRefs.fetchMessages.current?.(id),
    currentSessionId,
  })

  useNotifications()

  useEffect(() => {
    fetchSkills().then(setSkills)
    fetchWorkspaceFiles().then(setWorkspaceFiles)
  }, [])

  useEffect(() => {
    if (orbPanel.orbOpen) fetchSessionTree()
  }, [orbPanel.orbOpen, fetchSessionTree])

  const isChildSession = currentSessionId != null && sessions.treeRoots.some((r) =>
    r.children.some((c) => c.session_id === currentSessionId)
  )

  useEffect(() => {
    if (isChildSession) chat.setSendMode('sync')
  }, [isChildSession, chat.setSendMode])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    setShowScrollToBottom(false)
  }, [messages])

  const onChatScroll = useCallback(() => {
    const el = chatContainerRef.current
    if (!el) return
    const { scrollTop, scrollHeight, clientHeight } = el
    setShowScrollToBottom(scrollHeight - scrollTop - clientHeight > 80)
  }, [])

  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    setShowScrollToBottom(false)
  }, [])

  const switchToSession = useCallback(
    (newId: string) => {
      if (currentSessionId) {
        inputDraftsRef.current[currentSessionId] = chat.input
      }
      setCurrentSessionId(newId)
      chat.setInput(inputDraftsRef.current[newId] ?? '')
      switchToSessionBase(newId)
      orbPanel.setOrbOpen(false)
      fetchSessions(newId)
    },
    [
      currentSessionId,
      chat.input,
      chat.setInput,
      setCurrentSessionId,
      switchToSessionBase,
      orbPanel.setOrbOpen,
      fetchSessions,
      inputDraftsRef,
    ]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (
        e.key === 'Enter' &&
        !e.shiftKey &&
        !showSkillDropdown &&
        !showFileDropdown
      ) {
        e.preventDefault()
        chat.sendMessage(chat.input)
        return
      }
      if (e.key === '/' && !showSkillDropdown) {
        e.preventDefault()
        setShowSkillDropdown(true)
        setShowFileDropdown(false)
        setFileQuery('')
      } else if (e.key === '@' && !showFileDropdown) {
        e.preventDefault()
        setShowFileDropdown(true)
        setShowSkillDropdown(false)
        setFileQuery('')
      } else if (e.key === 'Escape') {
        setShowSkillDropdown(false)
        setShowFileDropdown(false)
      }
    },
    [
      showSkillDropdown,
      showFileDropdown,
      chat.input,
      chat.sendMessage,
    ]
  )

  return (
    <div className="app">
      <div className="main">
        <ChatArea
          currentSessionId={currentSessionId}
          allowBackground={!isChildSession}
          messages={messages}
          loading={chat.loading}
          sessionStatus={sessionStatus}
          liveTokens={chat.liveTokens}
          chatContainerRef={chatContainerRef}
          chatEndRef={chatEndRef}
          showScrollToBottom={showScrollToBottom}
          onChatScroll={onChatScroll}
          onScrollToBottom={scrollToBottom}
          input={chat.input}
          setInput={chat.setInput}
          selectedSkill={chat.selectedSkill}
          setSelectedSkill={chat.setSelectedSkill}
          skills={skills}
          workspaceFiles={workspaceFiles}
          showSkillDropdown={showSkillDropdown}
          setShowSkillDropdown={setShowSkillDropdown}
          showFileDropdown={showFileDropdown}
          setShowFileDropdown={setShowFileDropdown}
          fileQuery={fileQuery}
          setFileQuery={setFileQuery}
          sendMode={chat.sendMode}
          setSendMode={chat.setSendMode}
          onSend={() => chat.sendMessage(chat.input)}
          onKeyDown={handleKeyDown}
          inputRef={inputRef}
        />
        <OrbPanel
          currentSessionId={currentSessionId}
          orbOpen={orbPanel.orbOpen}
          setOrbOpen={orbPanel.setOrbOpen}
          orbPos={orbPanel.orbPos}
          orbPanelSize={orbPanel.orbPanelSize}
          paginatedRoots={orbPanel.paginatedRoots}
          paginatedTasks={orbPanel.paginatedTasks}
          paginatedSkills={orbPanel.paginatedSkills}
          paginatedWorkspace={orbPanel.paginatedWorkspace}
          sessionsPageCount={orbPanel.sessionsPageCount}
          tasksPageCount={orbPanel.tasksPageCount}
          skillsPageCount={orbPanel.skillsPageCount}
          workspacePageCount={orbPanel.workspacePageCount}
          safeSessionsPage={orbPanel.safeSessionsPage}
          safeTasksPage={orbPanel.safeTasksPage}
          safeSkillsPage={orbPanel.safeSkillsPage}
          safeWorkspacePage={orbPanel.safeWorkspacePage}
          setOrbSessionsPage={orbPanel.setOrbSessionsPage}
          setOrbTasksPage={orbPanel.setOrbTasksPage}
          setOrbSkillsPage={orbPanel.setOrbSkillsPage}
          setOrbWorkspacePage={orbPanel.setOrbWorkspacePage}
          selectedSkill={chat.selectedSkill}
          setSelectedSkill={chat.setSelectedSkill}
          onSwitchSession={switchToSession}
          onDeleteSession={handleDeleteSession}
          onNewSession={handleNewSession}
          onForkSession={handleForkSession}
          onResizePointerDown={orbPanel.handleOrbResizePointerDown}
          onOrbPointerDown={orbPanel.handleOrbPointerDown}
          onOrbPointerUp={orbPanel.handleOrbPointerUp}
          onOrbPointerCancel={orbPanel.handleOrbPointerCancel}
          onOrbClick={orbPanel.handleOrbClick}
          ORB_RESIZE_MIN={ORB_RESIZE_MIN}
        />
      </div>
    </div>
  )
}

export default App
