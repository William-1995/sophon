/**
 * Sessions hook - manages session list, tree, current session, messages.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { SESSION_STORAGE_KEY } from '../constants'
import * as sessionsApi from '../api/sessions'
import { loadGenUiForMessages } from '../utils/genUi'
import type { Session, TreeRoot, Message } from '../types'

interface UseSessionsResult {
  sessions: Session[]
  treeRoots: TreeRoot[]
  currentSessionId: string | null
  setCurrentSessionId: (id: string | null) => void
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  sessionStatus: string | null
  fetchSessions: (includeId?: string | null) => Promise<void>
  fetchSessionTree: (includeId?: string | null) => Promise<void>
  fetchMessages: (sessionId: string) => Promise<void>
  switchToSession: (newId: string) => void
  handleNewSession: () => Promise<void>
  handleDeleteSession: (sessionId: string, e: React.MouseEvent) => Promise<void>
  handleForkSession: () => Promise<void>
  refreshRefs: {
    fetchSessions: React.MutableRefObject<(() => void) | null>
    fetchSessionTree: React.MutableRefObject<(() => void) | null>
    fetchMessages: React.MutableRefObject<((id: string) => void) | null>
  }
}

export function useSessions(): UseSessionsResult {
  const [sessions, setSessions] = useState<Session[]>([])
  const [treeRoots, setTreeRoots] = useState<TreeRoot[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [sessionStatus, setSessionStatus] = useState<string | null>(null)

  const fetchSessionsRef = useRef<(() => void) | null>(null)
  const fetchSessionTreeRef = useRef<(() => void) | null>(null)
  const fetchMessagesRef = useRef<((id: string) => void) | null>(null)
  const currentSessionIdRef = useRef<string | null>(null)
  useEffect(() => {
    currentSessionIdRef.current = currentSessionId
  }, [currentSessionId])

  const fetchSessions = useCallback(async (includeId?: string | null) => {
    const include = includeId ?? currentSessionIdRef.current
    const list = await sessionsApi.listSessions(include)
    setSessions(list)
  }, [])

  const fetchSessionTree = useCallback(async (includeId?: string | null) => {
    const include = includeId ?? currentSessionIdRef.current
    const roots = await sessionsApi.listSessionTree(include)
    setTreeRoots(roots)
  }, [])

  const fetchMessages = useCallback(async (sessionId: string) => {
    const data = await sessionsApi.getMessages(sessionId)
    setSessionStatus(data.status ?? null)
    const baseMsgs = (data.messages ?? []).map((m) => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
      references: Array.isArray(m.references) ? m.references : undefined,
      timestamp: m.created_at != null ? m.created_at * 1000 : undefined,
    }))
    const msgs = loadGenUiForMessages(sessionId, baseMsgs)
    setMessages(msgs)
  }, [])

  useEffect(() => {
    fetchSessionsRef.current = () => fetchSessions()
    fetchSessionTreeRef.current = () => fetchSessionTree()
    fetchMessagesRef.current = fetchMessages
  }, [fetchSessions, fetchSessionTree, fetchMessages])

  useEffect(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(SESSION_STORAGE_KEY) : null
    fetchSessions(saved)
  }, [fetchSessions])

  useEffect(() => {
    if (currentSessionId) {
      fetchMessages(currentSessionId)
      try {
        localStorage.setItem(SESSION_STORAGE_KEY, currentSessionId)
      } catch {
        // ignore
      }
    } else {
      setMessages([])
      setSessionStatus(null)
    }
  }, [currentSessionId, fetchMessages])

  useEffect(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(SESSION_STORAGE_KEY) : null
    if (saved && sessions.some((s) => s.id === saved)) {
      setCurrentSessionId(saved)
    } else if (sessions.length > 0 && !currentSessionId) {
      setCurrentSessionId(sessions[0].id)
    }
  }, [sessions])

  const switchToSession = useCallback(
    (newId: string) => {
      setCurrentSessionId(newId)
      fetchMessages(newId)
      try {
        localStorage.setItem(SESSION_STORAGE_KEY, newId)
      } catch {
        // ignore
      }
    },
    [fetchMessages]
  )

  const handleNewSession = useCallback(async () => {
    const newId = await sessionsApi.createSession()
    setCurrentSessionId(newId)
    setMessages([])
    await fetchSessions(newId)
  }, [fetchSessions])

  const handleDeleteSession = useCallback(
    async (sessionId: string, e: React.MouseEvent) => {
      e.stopPropagation()
      await sessionsApi.deleteSession(sessionId)
      if (currentSessionId === sessionId) {
        const other = treeRoots.find((r) => r.id !== sessionId)
        const nextId =
          other?.id ??
          other?.children?.[0]?.session_id ??
          treeRoots.flatMap((r) => r.children).find((c) => c.session_id !== sessionId)?.session_id ??
          null
        setCurrentSessionId(nextId ?? null)
        if (nextId) fetchMessages(nextId)
        else setMessages([])
      }
      fetchSessionTree(currentSessionId === sessionId ? null : currentSessionId)
      fetchSessions()
    },
    [currentSessionId, treeRoots, fetchMessages, fetchSessionTree, fetchSessions]
  )

  const handleForkSession = useCallback(async () => {
    if (!currentSessionId) return
    const newId = await sessionsApi.forkSession(currentSessionId)
    const data = await sessionsApi.getMessages(newId)
    setCurrentSessionId(newId)
    setMessages(
      (data.messages ?? []).map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        references: Array.isArray(m.references) ? m.references : undefined,
        timestamp: m.created_at != null ? m.created_at * 1000 : undefined,
      }))
    )
    await fetchSessions(newId)
  }, [currentSessionId, fetchSessions])

  return {
    sessions,
    treeRoots,
    currentSessionId,
    setCurrentSessionId,
    messages,
    setMessages,
    sessionStatus,
    fetchSessions,
    fetchSessionTree,
    fetchMessages,
    switchToSession,
    handleNewSession,
    handleDeleteSession,
    handleForkSession,
    refreshRefs: {
      fetchSessions: fetchSessionsRef,
      fetchSessionTree: fetchSessionTreeRef,
      fetchMessages: fetchMessagesRef,
    },
  }
}
