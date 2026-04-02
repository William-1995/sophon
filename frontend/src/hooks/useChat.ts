/**
 * Chat hook - send message (async/sync), loading state, live tokens.
 */

import { useState, useCallback, useRef } from 'react'
import * as chatApi from '../api/chat'
import * as sessionsApi from '../api/sessions'
import * as resourcesApi from '../api/resources'
import { saveGenUi } from '../utils/genUi'
import type { Message, Skill } from '../types'
import type { DecisionRequired } from '../api/chat'

type SendMode = 'async' | 'sync'

interface UseChatOptions {
  currentSessionId: string | null
  setCurrentSessionId: (id: string | null) => void
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  fetchSessions: (includeId?: string | null) => Promise<void>
  setWorkspaceFiles: React.Dispatch<React.SetStateAction<string[]>>
  /** Optional: external ref for input drafts per session. If not provided, hook creates one. */
  inputDraftsRef?: React.MutableRefObject<Record<string, string>>
}

export interface LiveEvent {
  type: string
  [key: string]: unknown
}

export interface LiveTodo {
  id: string
  title: string
  status: 'pending' | 'in_progress' | 'done'
}

export interface InvestigationReport {
  intent?: string
  constraints?: string[]
  inputs_found?: string[]
  inputs_missing?: string[]
  candidate_files?: string[]
  usable_tools?: string[]
  blocked_reasons?: string[]
  ready_for_planning?: boolean
  recommended_next_action?: string
  planned_steps?: string[]
}

interface UseChatResult {
  input: string
  setInput: React.Dispatch<React.SetStateAction<string>>
  selectedSkill: Skill | null
  setSelectedSkill: React.Dispatch<React.SetStateAction<Skill | null>>
  loading: boolean
  liveTokens: number | null
  runId: string | null
  liveEvents: LiveEvent[]
  liveTodos: LiveTodo[]
  liveThinking: string[]
  investigationReport: InvestigationReport | null
  decisionRequired: DecisionRequired | null
  submitDecision: (choice: string) => Promise<void>
  sendMode: SendMode
  setSendMode: React.Dispatch<React.SetStateAction<SendMode>>
  sendMessage: (text: string, uploadedFiles?: string[]) => Promise<void>
  cancelRun: () => Promise<void>
  resumeRun: () => Promise<void>
  lastCancelledRunId: string | null
  inputDraftsRef: React.MutableRefObject<Record<string, string>>
}

export function useChat(options: UseChatOptions): UseChatResult {
  const internalRef = useRef<Record<string, string>>({})
  const inputDraftsRef = options.inputDraftsRef ?? internalRef
  const {
    currentSessionId,
    setCurrentSessionId,
    messages,
    setMessages,
    fetchSessions,
    setWorkspaceFiles,
  } = options

  const [input, setInput] = useState('')
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null)
  const [loading, setLoading] = useState(false)
  const [liveTokens, setLiveTokens] = useState<number | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [liveEvents, setLiveEvents] = useState<LiveEvent[]>([])
  const [liveTodos, setLiveTodos] = useState<LiveTodo[]>([])
  const [liveThinking, setLiveThinking] = useState<string[]>([])
  const [investigationReport, setInvestigationReport] = useState<InvestigationReport | null>(null)
  const [decisionRequired, setDecisionRequired] = useState<DecisionRequired | null>(null)
  const [sendMode, setSendMode] = useState<SendMode>('async')
  const [lastCancelledRunId, setLastCancelledRunId] = useState<string | null>(null)
  const runIdRef = useRef<string | null>(null)

  const handleSophonEvent = useCallback((evt: LiveEvent) => {
    setLiveEvents((prev) => [...prev.slice(-49), evt])
    if (evt.type === 'TODOS_PLAN' && Array.isArray(evt.items)) {
      setLiveTodos(evt.items as LiveTodo[])
    } else if (evt.type === 'TODOS_UPDATED' && Array.isArray(evt.items)) {
      setLiveTodos(evt.items as LiveTodo[])
    } else if (evt.type === 'THINKING' && typeof evt.content === 'string') {
      setLiveThinking((prev) => [...prev.slice(-11), evt.content as string])
      if (evt.payload && typeof evt.payload === 'object') {
        setInvestigationReport(evt.payload as InvestigationReport)
      }
    } else if (evt.type === 'INVESTIGATION_REPORT') {
      const payload = (evt.payload && typeof evt.payload === 'object' ? evt.payload : evt) as InvestigationReport
      setInvestigationReport(payload)
    }
  }, [])

  const submitDecision = useCallback(async (choice: string) => {
    if (decisionRequired?.runId) {
      try {
        await chatApi.submitDecision(decisionRequired.runId, choice)
        setDecisionRequired(null)
      } catch {
        // Ignore
      }
    }
  }, [decisionRequired?.runId])

  const cancelRun = useCallback(async () => {
    if (runId) {
      try {
        await chatApi.cancelRun(runId)
      } catch {
        // Ignore cancel errors
      }
    }
  }, [runId])

  const resumeRun = useCallback(async () => {
    const rid = lastCancelledRunId
    if (!rid || !currentSessionId || loading) return
    setLastCancelledRunId(null)
    setLoading(true)
    setLiveTokens(0)
    setRunId(null)
    setLiveEvents([])
    setLiveTodos([])
    setLiveThinking([])
    setInvestigationReport(null)
    setDecisionRequired(null)
    try {
      const result = await chatApi.sendStream(
        '[Resume]',
        selectedSkill?.name ?? null,
        currentSessionId,
        (tokens) => setLiveTokens(tokens),
        (data) => {
          if (data.type === 'CUSTOM' && data.name === 'sophon_event' && data.value) {
            handleSophonEvent(data.value as LiveEvent)
          }
        },
        (id) => {
          setRunId(id)
          runIdRef.current = id
        },
        (d) => setDecisionRequired(d),
        rid
      )
      if (result.sessionId && result.sessionId !== currentSessionId) {
        setCurrentSessionId(result.sessionId)
        await fetchSessions()
      }
      const assistantCount = messages.filter((x) => x.role === 'assistant').length
      saveGenUi(result.sessionId, assistantCount, result.genUi)
      setMessages((m) => {
        const prev = [...m]
        const lastIdx = prev.length - 1
        if (lastIdx >= 0 && prev[lastIdx].role === 'assistant' && prev[lastIdx].content === '[Run cancelled by user.]') {
          prev[lastIdx] = {
            ...prev[lastIdx],
            content: result.content,
            cacheHit: result.cacheHit,
            tokens: result.tokens,
            genUi: result.genUi,
            references: result.references?.length ? result.references : undefined,
            timestamp: Date.now(),
          }
          return prev
        }
        return [
          ...prev,
          {
            role: 'assistant' as const,
            content: result.content,
            cacheHit: result.cacheHit,
            tokens: result.tokens,
            genUi: result.genUi,
            references: result.references?.length ? result.references : undefined,
            timestamp: Date.now(),
          },
        ]
      })
      const files = await resourcesApi.fetchWorkspaceFiles()
      setWorkspaceFiles(files)
      await fetchSessions(result.sessionId)
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `Error: ${(err as Error).message}`, timestamp: Date.now() },
      ])
    } finally {
      setLoading(false)
      setLiveTokens(null)
      setRunId(null)
      setDecisionRequired(null)
    }
  }, [lastCancelledRunId, currentSessionId, loading, selectedSkill, messages, setMessages, setCurrentSessionId, fetchSessions, setWorkspaceFiles, handleSophonEvent])

  const sendMessage = useCallback(
    async (text: string, uploadedFiles: string[] = []) => {
      const trimmed = text.trim()
      if (!trimmed) return
      if (sendMode === 'sync' && loading) return

      let sessionId = currentSessionId
      if (!sessionId) {
        sessionId = await sessionsApi.createSession()
        setCurrentSessionId(sessionId)
        await fetchSessions()
      }

      if (sendMode === 'async') {
        try {
          const data = await chatApi.sendAsync(
            trimmed,
            selectedSkill?.name ?? null,
            sessionId,
            uploadedFiles
          )
          setInput('')
          setMessages((m) => [
            ...m,
            { role: 'user', content: `[Background] ${trimmed}`, skill: selectedSkill?.name, timestamp: Date.now() },
          ])
          if (data.child_session_id) {
            await fetchSessions(sessionId)
          }
        } catch (err) {
          setMessages((m) => [
            ...m,
            { role: 'assistant', content: `Error: ${(err as Error).message}`, timestamp: Date.now() },
          ])
        }
        return
      }

      setMessages((m) => [...m, { role: 'user', content: trimmed, skill: selectedSkill?.name, timestamp: Date.now() }])
      setInput('')
    setLoading(true)
    setRunId(null)
    setLiveEvents([])
    setLiveTodos([])
    setLiveThinking([])
    setInvestigationReport(null)
    setDecisionRequired(null)
    setLastCancelledRunId(null)

      try {
        const result = await chatApi.sendStream(
          trimmed,
          selectedSkill?.name ?? null,
          sessionId,
          (tokens) => setLiveTokens(tokens),
          (data) => {
            if (data.type === 'CUSTOM' && data.name === 'sophon_event' && data.value) {
              handleSophonEvent(data.value as LiveEvent)
            }
          },
          (id) => {
            setRunId(id)
            runIdRef.current = id
          },
          (d) => setDecisionRequired(d),
          null,
          uploadedFiles
        )

        if (result.cancelled && runIdRef.current) {
          setLastCancelledRunId(runIdRef.current)
        }
        if (result.sessionId && result.sessionId !== currentSessionId) {
          setCurrentSessionId(result.sessionId)
          await fetchSessions()
        }

        const assistantCount = messages.filter((x) => x.role === 'assistant').length
        saveGenUi(result.sessionId, assistantCount, result.genUi)

        setMessages((m) => {
          const next = [
            ...m,
            {
              role: 'assistant' as const,
              content: result.content,
              cacheHit: result.cacheHit,
              tokens: result.tokens,
              genUi: result.genUi,
              references:
                result.references.length > 0 ? result.references : undefined,
            },
          ]
          return next
        })

        const files = await resourcesApi.fetchWorkspaceFiles()
        setWorkspaceFiles(files)
        await fetchSessions(result.sessionId)
      } catch (err) {
        setMessages((m) => [
          ...m,
          { role: 'assistant', content: `Error: ${(err as Error).message}`, timestamp: Date.now() },
        ])
      } finally {
        setLoading(false)
        setLiveTokens(null)
        setRunId(null)
        setDecisionRequired(null)
      }
    },
    [
      currentSessionId,
      setCurrentSessionId,
      selectedSkill,
      sendMode,
      loading,
      messages,
      setMessages,
      fetchSessions,
      setWorkspaceFiles,
      handleSophonEvent,
    ]
  )

  return {
    input,
    setInput,
    selectedSkill,
    setSelectedSkill,
    loading,
    liveTokens,
    runId,
    liveEvents,
    liveTodos,
    liveThinking,
    investigationReport,
    decisionRequired,
    submitDecision,
    sendMode,
    setSendMode,
    sendMessage,
    cancelRun,
    resumeRun,
    lastCancelledRunId,
    inputDraftsRef,
  }
}
