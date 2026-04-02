/**
 * App - composition root. Orchestrates hooks and components.
 * Clean separation: hooks handle state/logic, components handle UI.
 */

import {
  useState,
  useEffect,
  useLayoutEffect,
  useRef,
  useCallback,
  type CSSProperties,
} from 'react'
import { useSessions } from './hooks/useSessions'
import { useChat } from './hooks/useChat'
import { useAppSidebar } from './hooks/useAppSidebar'
import { useEventSource } from './hooks/useEventSource'
import { useNotifications } from './hooks/useNotifications'
import { ChatArea } from './components/ChatArea/ChatArea'
import { DecisionModal } from './components/DecisionModal/DecisionModal'
import { AppSidebar } from './components/AppSidebar/AppSidebar'
import { CustomizeLayout } from './components/CustomizeLayout/CustomizeLayout'
import { CoworkPanel } from './components/CoworkPanel'
import {
  EMOTION_RING_COLORS,
  EMOTION_RING_DEFAULT,
} from './constants'
import { hexAlpha, hexToAccentRgbString } from './utils/color'
import {
  fetchEmotionLatest,
  fetchSkills,
  fetchWorkspaceFiles,
  uploadWorkspaceFiles,
} from './api/resources'
import './App.css'
import './cowork-styles.css'

function App() {
  const [skills, setSkills] = useState<{ name: string; description: string }[]>([])
  const [workspaceFiles, setWorkspaceFiles] = useState<string[]>([])
  const [showSkillDropdown, setShowSkillDropdown] = useState(false)
  const [showFileDropdown, setShowFileDropdown] = useState(false)
  const [fileQuery, setFileQuery] = useState('')
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)
  const [latestEmotion, setLatestEmotion] = useState<string | null>(null)
  const [showCowork, setShowCowork] = useState(false)
  /** Full-width 3-column customize shell (replaces workspace sidebar + main) */
  const [appShell, setAppShell] = useState<'workspace' | 'customize'>('workspace')
  const [customizeInitialSection, setCustomizeInitialSection] = useState<'overview' | 'settings'>('overview')
  /** Files chosen via picker; uploaded on Send → workspace/{user}/docs/ */
  const [pendingWorkspaceFiles, setPendingWorkspaceFiles] = useState<File[]>([])
  const [attachmentUploading, setAttachmentUploading] = useState(false)
  const [attachmentHint, setAttachmentHint] = useState<string | null>(null)

  const chatContainerRef = useRef<HTMLDivElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const appMainRef = useRef<HTMLDivElement>(null)
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

  const sidebar = useAppSidebar({
    treeRoots: sessions.treeRoots,
    skills,
    workspaceFiles,
  })

  useEventSource({
    onRefreshTree: () => refreshRefs.fetchSessionTree.current?.(),
    onRefreshSessions: () => refreshRefs.fetchSessions.current?.(),
    onRefreshMessages: (id) => refreshRefs.fetchMessages.current?.(id),
    onEmotionUpdated: (label) => setLatestEmotion(label ?? null),
    currentSessionId,
  })

  useNotifications()

  const refreshWorkspaceFiles = useCallback(async () => {
    const files = await fetchWorkspaceFiles()
    setWorkspaceFiles(files)
  }, [])

  useEffect(() => {
    fetchSkills().then(setSkills)
    refreshWorkspaceFiles()
  }, [refreshWorkspaceFiles])

  // Initialize theme from localStorage; default is system via CSS media queries.
  useEffect(() => {
    const savedTheme = localStorage.getItem('sophon-theme')
    if (savedTheme === 'warm' || savedTheme === 'light' || savedTheme === 'dark') {
      document.documentElement.setAttribute('data-theme', savedTheme)
      return
    }
    document.documentElement.removeAttribute('data-theme')
  }, [])

  useEffect(() => {
    fetchEmotionLatest().then((r) => setLatestEmotion(r.emotion_label ?? null))
  }, [])

  // Keep session tree up to date so we can reliably detect child sessions
  useEffect(() => {
    if (currentSessionId) {
      fetchSessionTree(currentSessionId)
    }
  }, [currentSessionId, fetchSessionTree])

  useEffect(() => {
    void fetchSessionTree()
  }, [fetchSessionTree])

  /** Composer max width follows this column’s real width (sidebar open/closed updates reliably). */
  useLayoutEffect(() => {
    const el = appMainRef.current
    if (!el) return
    const apply = () => {
      const w = el.getBoundingClientRect().width
      const max = Math.min(1600, Math.max(240, Math.floor(w - 48)))
      el.style.setProperty('--chat-composer-max', `${max}px`)
    }
    apply()
    const ro = new ResizeObserver(apply)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  /**
   * When skill/file UI has focus (chips, filter), textarea key handler does not run.
   * Still allow Esc, second `/` or `@` to dismiss without picking an item.
   */
  useEffect(() => {
    if (!showSkillDropdown && !showFileDropdown) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        setShowSkillDropdown(false)
        setShowFileDropdown(false)
        inputRef.current?.focus()
        return
      }
      if (e.target instanceof HTMLTextAreaElement) return

      if (showSkillDropdown && e.key === '/') {
        e.preventDefault()
        setShowSkillDropdown(false)
        inputRef.current?.focus()
        return
      }
      if (showFileDropdown && e.key === '@') {
        const t = e.target
        if (
          t instanceof HTMLInputElement &&
          t.hasAttribute('data-composer-file-filter')
        ) {
          return
        }
        e.preventDefault()
        setShowFileDropdown(false)
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKeyDown, true)
    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [showSkillDropdown, showFileDropdown])

  /* Emotion → global accent (whole UI, not only sidebar ring) */
  useEffect(() => {
    const root = document.documentElement
    const label = latestEmotion?.toLowerCase().trim()
    if (label && EMOTION_RING_COLORS[label]) {
      const hex = EMOTION_RING_COLORS[label]
      root.style.setProperty('--emotion-accent', hex)
      root.style.setProperty('--emotion-accent-dim', hexAlpha(hex, 0.22))
      root.style.setProperty('--accent-rgb', hexToAccentRgbString(hex))
    } else if (label) {
      const hex = EMOTION_RING_DEFAULT
      root.style.setProperty('--emotion-accent', hex)
      root.style.setProperty('--emotion-accent-dim', hexAlpha(hex, 0.18))
      root.style.setProperty('--accent-rgb', hexToAccentRgbString(hex))
    } else {
      root.style.removeProperty('--emotion-accent')
      root.style.removeProperty('--emotion-accent-dim')
      root.style.removeProperty('--accent-rgb')
    }
  }, [latestEmotion])

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
      setPendingWorkspaceFiles([])
      switchToSessionBase(newId)
      sidebar.setSidebarCollapsed(false)
      fetchSessions(newId)
    },
    [
      currentSessionId,
      chat.input,
      chat.setInput,
      setCurrentSessionId,
      switchToSessionBase,
      sidebar.setSidebarCollapsed,
      fetchSessions,
      inputDraftsRef,
    ]
  )

  const handleSend = useCallback(async () => {
    if (attachmentUploading) return
    if (chat.sendMode === 'sync' && chat.loading) return

    let finalText = chat.input.trim()
    let uploadedWorkspaceFiles: string[] = []
    if (!finalText && pendingWorkspaceFiles.length === 0) return

    if (pendingWorkspaceFiles.length > 0) {
      const userTextBeforeUpload = chat.input.trim()
      setAttachmentHint(null)
      setAttachmentUploading(true)
      try {
        const r = await uploadWorkspaceFiles(pendingWorkspaceFiles, 'docs')
        await refreshWorkspaceFiles()
        uploadedWorkspaceFiles = r.saved
        const refs = r.saved.map((p) => `@${p}`).join(' ')
        finalText = [userTextBeforeUpload, refs].filter(Boolean).join(' ').trim()
        setPendingWorkspaceFiles([])

        if (r.errors?.length) {
          const errLine = r.errors.map((e) => `${e.name}: ${e.error}`).join('; ')
          setAttachmentHint(`Some files failed: ${errLine}`)
          window.setTimeout(() => setAttachmentHint(null), 8000)
        }
        if (!finalText) {
          setAttachmentHint((h) => h ?? 'No files were saved')
          setAttachmentUploading(false)
          return
        }
        if (!userTextBeforeUpload && r.saved.length > 0 && !r.errors?.length) {
          setAttachmentHint(`Uploaded ${r.saved.length} file(s) and attached them to the conversation`)
          window.setTimeout(() => setAttachmentHint(null), 8000)
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Upload failed'
        setAttachmentHint(msg)
        window.setTimeout(() => setAttachmentHint(null), 8000)
        setAttachmentUploading(false)
        return
      }
      setAttachmentUploading(false)
    }

    await chat.sendMessage(finalText, uploadedWorkspaceFiles)
  }, [
    attachmentUploading,
    pendingWorkspaceFiles,
    refreshWorkspaceFiles,
    chat.sendMessage,
    chat.input,
    chat.loading,
    chat.sendMode,
  ])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (
        e.key === 'Enter' &&
        !e.shiftKey &&
        !showSkillDropdown &&
        !showFileDropdown
      ) {
        e.preventDefault()
        void handleSend()
        return
      }
      if (e.key === 'Escape') {
        setShowSkillDropdown(false)
        setShowFileDropdown(false)
        return
      }

      const el = e.currentTarget
      const pos = el.selectionStart ?? el.value.length
      const textBefore = el.value.slice(0, pos)
      const lineStart = textBefore.lastIndexOf('\n') + 1
      const currentLine = textBefore.slice(lineStart)
      /** `/` opens skill only on a blank line so paths and URLs are not hijacked */
      const slashOpensSkill = /^\s*$/.test(currentLine)
      /** `@` opens file picker only after start-of-message or whitespace */
      const atOpensFile =
        textBefore.length === 0 || /[\s\n]$/.test(textBefore)

      /* Same key again closes the menu — no forced pick */
      if (e.key === '/' && slashOpensSkill) {
        e.preventDefault()
        if (showSkillDropdown) {
          setShowSkillDropdown(false)
        } else {
          setShowSkillDropdown(true)
          setShowFileDropdown(false)
          setFileQuery('')
        }
        return
      }
      if (e.key === '@' && atOpensFile) {
        e.preventDefault()
        if (showFileDropdown) {
          setShowFileDropdown(false)
        } else {
          setShowFileDropdown(true)
          setShowSkillDropdown(false)
          setFileQuery('')
        }
      }
    },
    [showSkillDropdown, showFileDropdown, handleSend]
  )

  const appStyle = {
    '--sidebar-width':
      appShell === 'customize'
        ? '0px'
        : sidebar.sidebarCollapsed
          ? '52px'
          : '260px',
  } as CSSProperties

  const openCustomize = useCallback(() => {
    setShowCowork(false)
    setCustomizeInitialSection('overview')
    setAppShell('customize')
  }, [])

  const openSettings = useCallback(() => {
    setShowCowork(false)
    setCustomizeInitialSection('settings')
    setAppShell('customize')
  }, [])

  return (
    <div className="app" style={appStyle}>
      {chat.decisionRequired && (
        <DecisionModal
          data={chat.decisionRequired}
          onSubmit={(c) => chat.submitDecision(c)}
        />
      )}
      
      {appShell === 'customize' ? (
        <div className="app-shell app-shell--customize">
          <CustomizeLayout
            skills={skills}
            initialSection={customizeInitialSection}
            onBack={() => setAppShell('workspace')}
            onPickSkill={chat.setSelectedSkill}
          />
        </div>
      ) : (
        <div className="app-shell">
          <AppSidebar
            currentSessionId={currentSessionId}
            collapsed={sidebar.sidebarCollapsed}
            onToggleCollapse={sidebar.toggleSidebar}
            paginatedRoots={sidebar.paginatedRoots}
            paginatedTasks={sidebar.paginatedTasks}
            paginatedSkills={sidebar.paginatedSkills}
            paginatedWorkspace={sidebar.paginatedWorkspace}
            sessionsPageCount={sidebar.sessionsPageCount}
            tasksPageCount={sidebar.tasksPageCount}
            skillsPageCount={sidebar.skillsPageCount}
            workspacePageCount={sidebar.workspacePageCount}
            safeSessionsPage={sidebar.safeSessionsPage}
            safeTasksPage={sidebar.safeTasksPage}
            safeSkillsPage={sidebar.safeSkillsPage}
            safeWorkspacePage={sidebar.safeWorkspacePage}
            setSidebarSessionsPage={sidebar.setSidebarSessionsPage}
            setSidebarTasksPage={sidebar.setSidebarTasksPage}
            setSidebarSkillsPage={sidebar.setSidebarSkillsPage}
            setSidebarWorkspacePage={sidebar.setSidebarWorkspacePage}
            selectedSkill={chat.selectedSkill}
            setSelectedSkill={chat.setSelectedSkill}
            onSwitchSession={switchToSession}
            onDeleteSession={handleDeleteSession}
            onNewSession={handleNewSession}
            onForkSession={handleForkSession}
            onOpenCustomize={openCustomize}
            onOpenSettings={openSettings}
          />

          <div className="app-main" ref={appMainRef}>
            <header className="app-header">
              <div className="header-tabs">
                <button
                  type="button"
                  className={!showCowork ? 'active' : ''}
                  onClick={() => setShowCowork(false)}
                >
                  Chat
                </button>
                <button
                  type="button"
                  className={showCowork ? 'active' : ''}
                  onClick={() => setShowCowork(true)}
                >
                  Workflow
                </button>
              </div>
            </header>

            {!showCowork ? (
              <ChatArea
                latestEmotion={latestEmotion}
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
                onSend={() => void handleSend()}
                pendingWorkspaceFiles={pendingWorkspaceFiles}
                onAddPendingWorkspaceFiles={(files) =>
                  setPendingWorkspaceFiles((prev) => [...prev, ...files])
                }
                onRemovePendingWorkspaceFile={(index) =>
                  setPendingWorkspaceFiles((prev) => prev.filter((_, i) => i !== index))
                }
                attachmentUploading={attachmentUploading}
                attachmentHint={attachmentHint}
                onCancel={chat.cancelRun}
                onResume={chat.resumeRun}
                onNewSession={handleNewSession}
                lastCancelledRunId={chat.lastCancelledRunId}
                runId={chat.runId}
                liveEvents={chat.liveEvents}
                liveTodos={chat.liveTodos}
                liveThinking={chat.liveThinking}
                investigationReport={chat.investigationReport}
                onKeyDown={handleKeyDown}
                inputRef={inputRef}
              />
            ) : (
              <CoworkPanel
                isOpen={showCowork}
                onClose={() => setShowCowork(false)}
                workspaceFiles={workspaceFiles}
                onRefreshWorkspaceFiles={refreshWorkspaceFiles}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default App
