/**
 * Chat hook - send message (async/sync), loading state, live tokens.
 */

import { useState, useCallback, useRef } from 'react'
import * as chatApi from '../api/chat'
import * as sessionsApi from '../api/sessions'
import * as resourcesApi from '../api/resources'
import { saveGenUi } from '../utils/genUi'
import type { Message, Skill } from '../types'

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

interface UseChatResult {
  input: string
  setInput: React.Dispatch<React.SetStateAction<string>>
  selectedSkill: Skill | null
  setSelectedSkill: React.Dispatch<React.SetStateAction<Skill | null>>
  loading: boolean
  liveTokens: number | null
  sendMode: SendMode
  setSendMode: React.Dispatch<React.SetStateAction<SendMode>>
  sendMessage: (text: string) => Promise<void>
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
  const [sendMode, setSendMode] = useState<SendMode>('async')

  const sendMessage = useCallback(
    async (text: string) => {
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
            sessionId
          )
          setInput('')
          setMessages((m) => [
            ...m,
            { role: 'user', content: `[Background] ${trimmed}`, skill: selectedSkill?.name },
          ])
          if (data.child_session_id) {
            await fetchSessions(sessionId)
          }
        } catch (err) {
          setMessages((m) => [
            ...m,
            { role: 'assistant', content: `Error: ${(err as Error).message}` },
          ])
        }
        return
      }

      setMessages((m) => [...m, { role: 'user', content: trimmed, skill: selectedSkill?.name }])
      setInput('')
      setLoading(true)
      setLiveTokens(0)

      try {
        const result = await chatApi.sendStream(
          trimmed,
          selectedSkill?.name ?? null,
          sessionId,
          (tokens) => setLiveTokens(tokens),
          () => {}
        )

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
          { role: 'assistant', content: `Error: ${(err as Error).message}` },
        ])
      } finally {
        setLoading(false)
        setLiveTokens(null)
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
    ]
  )

  return {
    input,
    setInput,
    selectedSkill,
    setSelectedSkill,
    loading,
    liveTokens,
    sendMode,
    setSendMode,
    sendMessage,
    inputDraftsRef,
  }
}
