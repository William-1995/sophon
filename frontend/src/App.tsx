import { useState, useEffect, useRef, useCallback } from 'react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || ''
const SESSION_STORAGE_KEY = 'sophon_current_session'
const GEN_UI_PREFIX = 'sophon_gen_ui:'

interface Skill {
  name: string
  description: string
}

interface Session {
  id: string
  message_count: number
  updated_at: number | null
}

interface ChildSession {
  session_id: string
  parent_id: string | null
  title: string
  agent: string
  kind: string
  status: string
  created_at: number
  updated_at: number
}

interface TreeRoot {
  id: string
  message_count: number
  updated_at: number | null
  children: ChildSession[]
}

interface Reference {
  title?: string
  url: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  skill?: string
  cacheHit?: boolean
  tokens?: number
  genUi?: { type: string; payload?: unknown }
  references?: Reference[]
}

function App() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [workspaceFiles, setWorkspaceFiles] = useState<string[]>([])
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null)
  const [input, setInput] = useState('')
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [liveTokens, setLiveTokens] = useState<number | null>(null)
  const [orbOpen, setOrbOpen] = useState(false)
  const [orbPos, setOrbPos] = useState<{ x: number; y: number } | null>(null)
  const orbDragRef = useRef<{ startX: number; startY: number; startPos: { x: number; y: number } } | null>(null)
  const orbJustDraggedRef = useRef(false)
  const [showSkillDropdown, setShowSkillDropdown] = useState(false)
  const [showFileDropdown, setShowFileDropdown] = useState(false)
  const [fileQuery, setFileQuery] = useState('')
  const chatEndRef = useRef<HTMLDivElement>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const inputDraftsRef = useRef<Record<string, string>>({})
  const [sendMode, setSendMode] = useState<'async' | 'sync'>('async')
  const [treeRoots, setTreeRoots] = useState<TreeRoot[]>([])
  const [sessionStatus, setSessionStatus] = useState<string | null>(null)
  const [orbPanelSize, setOrbPanelSize] = useState({ width: 280, height: 420 })
  const [orbSessionsPage, setOrbSessionsPage] = useState(0)
  const [orbTasksPage, setOrbTasksPage] = useState(0)
  const [orbSkillsPage, setOrbSkillsPage] = useState(0)
  const [orbWorkspacePage, setOrbWorkspacePage] = useState(0)
  const orbResizeRef = useRef<{ startX: number; startY: number; startW: number; startH: number } | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const fetchSessionsRef = useRef<(() => void) | null>(null)
  const fetchSessionTreeRef = useRef<(() => void) | null>(null)
  const fetchMessagesRef = useRef<((id: string) => void) | null>(null)
  const currentSessionIdRef = useRef<string | null>(null)

  const fetchSessions = useCallback(async (includeId?: string | null) => {
    const include = includeId ?? currentSessionId
    const qs = include ? `?include=${encodeURIComponent(include)}` : ''
    const res = await fetch(`${API_BASE}/api/sessions${qs}`)
    const data = await res.json()
    setSessions(data.sessions || [])
  }, [currentSessionId])

  const fetchSessionTree = useCallback(async (includeId?: string | null) => {
    try {
      const include = includeId ?? currentSessionId
      const qs = include ? `?tree=1&include=${encodeURIComponent(include)}` : '?tree=1'
      const res = await fetch(`${API_BASE}/api/sessions${qs}`)
      const data = await res.json()
      setTreeRoots(data.roots || [])
    } catch {
      setTreeRoots([])
    }
  }, [currentSessionId])

  const fetchMessages = useCallback(async (sessionId: string) => {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages`)
    const data = await res.json()
    setSessionStatus((data as { status?: string }).status ?? null)
    const baseMsgs = (data.messages || []).map((m: { role: string; content: string; references?: Reference[] }) => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
      references: Array.isArray(m.references) ? m.references : undefined
    }))
    try {
      const stored = localStorage.getItem(GEN_UI_PREFIX + sessionId)
      const genUiMap: Record<string, unknown> = stored ? JSON.parse(stored) : {}
      const isValidGenUi = (v: unknown): v is { type: string; payload?: unknown } =>
        v != null && typeof v === 'object' && 'type' in v && (v as { payload?: unknown }).payload != null
      let ai = 0
      const msgs = baseMsgs.map((m: { role: string; content: string; references?: Reference[] }) => {
        if (m.role !== 'assistant') return m
        const gu = genUiMap[String(ai)]
        ai += 1
        return { ...m, genUi: isValidGenUi(gu) ? gu : undefined }
      })
      setMessages(msgs)
    } catch {
      setMessages(baseMsgs)
    }
  }, [])

  useEffect(() => {
    fetchSessionsRef.current = fetchSessions
    fetchSessionTreeRef.current = fetchSessionTree
    fetchMessagesRef.current = fetchMessages
    currentSessionIdRef.current = currentSessionId
  }, [fetchSessions, fetchSessionTree, fetchMessages, currentSessionId])

  useEffect(() => {
    fetch(`${API_BASE}/api/skills`).then(r => r.json()).then(d => setSkills(d.skills || []))
    fetch(`${API_BASE}/api/workspace/files`).then(r => r.json()).then(d => setWorkspaceFiles(d.files || []))
  }, [])

  useEffect(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(SESSION_STORAGE_KEY) : null
    fetchSessions(saved)
  }, [fetchSessions])

  useEffect(() => {
    if (currentSessionId) {
      fetchMessages(currentSessionId)
      try { localStorage.setItem(SESSION_STORAGE_KEY, currentSessionId) } catch (_) {}
    } else {
      setMessages([])
      setSessionStatus(null)
    }
  }, [currentSessionId, fetchMessages])

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

  const switchToSession = useCallback((newId: string) => {
    if (currentSessionId) inputDraftsRef.current[currentSessionId] = input
    setCurrentSessionId(newId)
    setInput(inputDraftsRef.current[newId] ?? '')
    try { localStorage.setItem(SESSION_STORAGE_KEY, newId) } catch (_) {}
    fetchMessages(newId)
    setOrbOpen(false)
    fetchSessions(newId)
  }, [currentSessionId, input, fetchMessages, fetchSessions])

  useEffect(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(SESSION_STORAGE_KEY) : null
    if (saved && sessions.some(s => s.id === saved)) {
      setCurrentSessionId(saved)
    } else if (sessions.length > 0 && !currentSessionId) {
      setCurrentSessionId(sessions[0].id)
    }
  }, [sessions])

  useEffect(() => {
    if (orbOpen) fetchSessionTree()
  }, [orbOpen, fetchSessionTree])

  useEffect(() => {
    const url = `${API_BASE}/api/events`
    const es = new EventSource(url)
    eventSourceRef.current = es
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as Record<string, unknown>
        const type = String(data.type ?? '')
        if (type === 'heartbeat') return
        if (type === 'TASK_STARTED' || type === 'TASK_FINISHED' || type === 'TASK_ERROR') {
          fetchSessionTreeRef.current?.()
          fetchSessionsRef.current?.()
          const tid = data.threadId as string | undefined
          if (tid && tid === currentSessionIdRef.current) {
            fetchMessagesRef.current?.(tid)
          }
        }
        if (type === 'TASK_FINISHED') {
          const label = (data.label as string) || 'Task finished'
          if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification('Sophon', { body: label })
          }
        }
        if (type === 'TASK_ERROR') {
          const msg = (data.message as string) || 'Task failed'
          if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification('Sophon Error', { body: msg })
          }
        }
      } catch (_) {}
    }
    es.onerror = () => {
      es.close()
      eventSourceRef.current = null
    }
    return () => {
      es.close()
      eventSourceRef.current = null
    }
  }, [])

  useEffect(() => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  const filteredFiles = fileQuery
    ? workspaceFiles.filter(f => f.toLowerCase().includes(fileQuery.toLowerCase()))
    : workspaceFiles

  const handleNewSession = async () => {
    const res = await fetch(`${API_BASE}/api/sessions`, { method: 'POST' })
    const data = await res.json()
    const newId = data.session_id
    setCurrentSessionId(newId)
    setMessages([])
    const listRes = await fetch(`${API_BASE}/api/sessions?include=${encodeURIComponent(newId)}`)
    const listData = await listRes.json()
    setSessions(listData.sessions || [])
  }

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, { method: 'DELETE' })
    if (!res.ok) return
    if (currentSessionId === sessionId) {
      const other = treeRoots.find(r => r.id !== sessionId)
      const nextId = other?.id ?? other?.children?.[0]?.session_id ?? treeRoots.flatMap(r => r.children).find(c => c.session_id !== sessionId)?.session_id ?? null
      setCurrentSessionId(nextId ?? null)
      if (nextId) fetchMessages(nextId)
      else setMessages([])
    }
    fetchSessionTree(currentSessionId === sessionId ? null : currentSessionId)
    fetchSessions()
  }

  const handleForkSession = async () => {
    if (!currentSessionId) return
    const res = await fetch(`${API_BASE}/api/sessions/${currentSessionId}/fork`, { method: 'POST' })
    const data = await res.json()
    const newId = data.session_id
    setCurrentSessionId(newId)
    const msgRes = await fetch(`${API_BASE}/api/sessions/${newId}/messages`)
    const msgData = await msgRes.json()
    setMessages((msgData.messages || []).map((m: { role: string; content: string }) => ({ role: m.role as 'user' | 'assistant', content: m.content })))
    const listRes = await fetch(`${API_BASE}/api/sessions?include=${encodeURIComponent(newId)}`)
    const listData = await listRes.json()
    setSessions(listData.sessions || [])
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !showSkillDropdown && !showFileDropdown) {
      e.preventDefault()
      sendMessage()
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
  }

  const sendMessage = async () => {
    const text = input.trim()
    if (!text) return
    const isAsync = sendMode === 'async'
    if (!isAsync && loading) return

    let sessionId = currentSessionId
    if (!sessionId) {
      const res = await fetch(`${API_BASE}/api/sessions`, { method: 'POST' })
      const data = await res.json()
      sessionId = data.session_id
      setCurrentSessionId(sessionId)
      fetchSessions()
    }

    if (isAsync) {
      try {
        const res = await fetch(`${API_BASE}/api/chat/async`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            skill: selectedSkill?.name || null,
            session_id: sessionId
          })
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setInput('')
        setMessages(m => [...m, { role: 'user', content: `[Background] ${text}`, skill: selectedSkill?.name }])
        if (data.child_session_id && sessionId) {
          fetchSessionTree(sessionId)
          fetchSessions()
        }
      } catch (err) {
        setMessages(m => [...m, { role: 'assistant', content: `Error: ${(err as Error).message}` }])
      }
      return
    }

    setMessages(m => [...m, { role: 'user', content: text, skill: selectedSkill?.name }])
    setInput('')
    setLoading(true)
    setLiveTokens(0)

    try {
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          skill: selectedSkill?.name || null,
          session_id: sessionId
        })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      if (!res.body) throw new Error('No response body')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let finalAnswer = ''
      let finalTokens = 0
      let finalCacheHit = false
      let finalGenUi: Message['genUi'] = undefined
      let finalReferences: Reference[] = []
      let finalSessionId = sessionId

      const processAgUiEvent = (data: Record<string, unknown>) => {
        const type = String(data.type ?? '')
        if (type === 'CUSTOM') {
          const name = data.name as string
          const value = data.value as Record<string, unknown> | undefined
          if (name === 'progress' && value && typeof value.tokens === 'number') setLiveTokens(value.tokens)
          if (name === 'gen_ui') finalGenUi = value as Message['genUi']
        } else if (type === 'TEXT_MESSAGE_CONTENT' && typeof data.delta === 'string') {
          finalAnswer += data.delta
        } else if (type === 'RUN_FINISHED') {
          const result = (data.result ?? {}) as Record<string, unknown>
          finalSessionId = (result.session_id as string) ?? sessionId
          finalTokens = (result.tokens as number) ?? 0
          finalCacheHit = (result.cache_hit as boolean) ?? false
          if (result.gen_ui != null) finalGenUi = result.gen_ui as Message['genUi']
          if (Array.isArray(result.references)) finalReferences = result.references as Reference[]
        } else if (type === 'RUN_ERROR') {
          throw new Error((data.message as string) ?? 'Unknown error')
        }
        // Legacy fallback for old SSE format (progress, done, error)
        if (type === 'progress' && typeof data.tokens === 'number') setLiveTokens(data.tokens)
        if (type === 'done') {
          finalAnswer = (data.answer as string) ?? ''
          finalSessionId = (data.session_id as string) ?? sessionId
          finalTokens = (data.tokens as number) ?? 0
          finalCacheHit = (data.cache_hit as boolean) ?? false
          finalGenUi = data.gen_ui as Message['genUi'] | undefined
          if (Array.isArray(data.references)) finalReferences = data.references as Reference[]
        }
        if (type === 'error') throw new Error((data.error as string) ?? 'Unknown error')
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const block of parts) {
          const dataIdx = block.indexOf('data: ')
          if (dataIdx !== 0) continue
          try {
            const data = JSON.parse(block.slice(6)) as Record<string, unknown>
            processAgUiEvent(data)
          } catch (e) {
            if (e instanceof SyntaxError) continue
            throw e
          }
        }
      }
      if (buffer) {
        const dataIdx = buffer.indexOf('data: ')
        if (dataIdx === 0) {
          try {
            const data = JSON.parse(buffer.slice(6)) as Record<string, unknown>
            processAgUiEvent(data)
          } catch (e) {
            if (!(e instanceof SyntaxError)) throw e
          }
        }
      }

      if (finalSessionId && finalSessionId !== currentSessionId) {
        setCurrentSessionId(finalSessionId)
        fetchSessions()
      }
      setMessages(m => {
        const next = [...m, {
          role: 'assistant' as const,
          content: finalAnswer,
          cacheHit: finalCacheHit,
          tokens: finalTokens,
          genUi: finalGenUi,
          references: finalReferences.length ? finalReferences : undefined
        }]
        if (finalGenUi && finalSessionId) {
          try {
            const sid = finalSessionId
            const prev = localStorage.getItem(GEN_UI_PREFIX + sid)
            const map: Record<string, unknown> = prev ? JSON.parse(prev) : {}
            const ai = m.filter(x => x.role === 'assistant').length
            map[String(ai)] = finalGenUi
            localStorage.setItem(GEN_UI_PREFIX + sid, JSON.stringify(map))
          } catch (_) {}
        }
        return next
      })
      fetch(`${API_BASE}/api/workspace/files`).then(r => r.json()).then(d => setWorkspaceFiles(d.files || []))
      const listRes = await fetch(`${API_BASE}/api/sessions${finalSessionId ? '?include=' + encodeURIComponent(finalSessionId) : ''}`)
      const listData = await listRes.json()
      setSessions(listData.sessions || [])
    } catch (err) {
      setMessages(m => [...m, { role: 'assistant', content: `Error: ${(err as Error).message}` }])
    } finally {
      setLoading(false)
      setLiveTokens(null)
    }
  }

  const LINE_COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
  const labelFromKind = (kind: string) => kind.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  const parseA2uiValueMap = (arr: { key: string; valueString?: string; valueNumber?: number; valueMap?: unknown[] }[]): Record<string, unknown> | unknown[] => {
    const out: Record<string, unknown> = {}
    for (const e of arr) {
      if (e.valueMap != null) out[e.key] = parseA2uiValueMap(e.valueMap as { key: string; valueString?: string; valueNumber?: number; valueMap?: unknown[] }[])
      else if (e.valueNumber != null) out[e.key] = e.valueNumber
      else out[e.key] = e.valueString ?? ''
    }
    const keys = Object.keys(out).filter((k) => /^\d+$/.test(k))
    if (keys.length === Object.keys(out).length && keys.length > 0) return Object.keys(out).sort((a, b) => parseInt(a, 10) - parseInt(b, 10)).map((k) => out[k])
    return out
  }
  const extractChartsFromA2ui = (messages: { dataModelUpdate?: { contents?: { key: string; valueMap?: unknown[] }[] } }[]): { kind: string; labels?: string[]; values?: number[]; x?: string[]; y?: number[]; chart_type?: string }[] => {
    const dm = messages.find((m) => m.dataModelUpdate?.contents)
    if (!dm?.dataModelUpdate?.contents) return []
    const chartsEntry = dm.dataModelUpdate.contents.find((c: { key: string }) => c.key === 'charts') as { valueMap?: { key: string; valueMap?: unknown[] }[] }
    if (!chartsEntry?.valueMap) return []
    return chartsEntry.valueMap.map((item) => {
      const raw = parseA2uiValueMap((item.valueMap ?? []) as { key: string; valueString?: string; valueNumber?: number; valueMap?: unknown[] }[])
      const data = (typeof raw === 'object' && raw !== null && !Array.isArray(raw)) ? raw : {} as Record<string, unknown>
      return {
        kind: String(data.kind ?? 'chart'),
        labels: Array.isArray(data.labels) ? data.labels.map(String) : undefined,
        values: Array.isArray(data.values) ? data.values.map(Number) : undefined,
        x: Array.isArray(data.x) ? data.x.map(String) : undefined,
        y: Array.isArray(data.y) ? data.y.map(Number) : undefined,
        chart_type: String(data.chart_type ?? 'bar'),
      }
    })
  }
  const renderGenUi = (genUi: { type?: string; format?: string; payload?: unknown; messages?: unknown[] }) => {
    if (genUi?.format === 'a2ui' && Array.isArray(genUi.messages) && genUi.messages.length > 0) {
      const charts = extractChartsFromA2ui(genUi.messages as { dataModelUpdate?: { contents?: { key: string; valueMap?: unknown[] }[] } }[])
      if (charts.length > 0) {
        return (
          <div className="gen-ui-chart">
            {charts.map((c, i) => {
              const title = labelFromKind(c.kind ?? 'chart')
              const isLine = c.chart_type === 'line' || (c.x != null && c.y != null && c.labels == null)
              const labels = c.labels ?? c.x ?? []
              const values = c.values ?? c.y ?? []
              const data = labels.map((l, j) => ({ name: l, value: values[j] ?? 0 }))
              if (data.length === 0) return null
              return (
                <div key={title + String(i)}>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>{title}</div>
                  <ResponsiveContainer width="100%" height={180}>
                    {isLine ? (
                      <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Line type="monotone" dataKey="value" stroke={LINE_COLORS[i % LINE_COLORS.length]} name={title} dot={{ r: 2 }} strokeWidth={2} />
                      </LineChart>
                    ) : (
                      <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="value" fill={LINE_COLORS[i % LINE_COLORS.length]} />
                      </BarChart>
                    )}
                  </ResponsiveContainer>
                </div>
              )
            })}
          </div>
        )
      }
    }
    if (!genUi?.payload && genUi?.format !== 'a2ui') return null
    const p = (genUi?.payload ?? {}) as { data?: { x?: string[]; y?: number[] } | Record<string, unknown>[]; multi_series?: boolean; labels?: string[]; values?: number[]; series_labels?: Record<string, string>; charts?: { kind?: string; label?: string; labels?: string[]; values?: number[]; x?: string[]; y?: number[]; chart_type?: string }[] }
    if (Array.isArray(p.charts) && p.charts.length > 0) {
      return (
        <div className="gen-ui-chart">
          {p.charts.map((c, i) => {
            const title = c.label ?? labelFromKind(c.kind ?? 'chart')
            const isLine = c.chart_type === 'line' || (c.x != null && c.y != null && c.labels == null)
            const labels = c.labels ?? c.x ?? []
            const values = c.values ?? c.y ?? []
            const data = labels.map((l, j) => ({ name: l, value: values[j] ?? 0 }))
            if (data.length === 0) return null
            return (
              <div key={title + String(i)}>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>{title}</div>
                <ResponsiveContainer width="100%" height={180}>
                  {isLine ? (
                    <LineChart data={data}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Line type="monotone" dataKey="value" stroke={LINE_COLORS[i % LINE_COLORS.length]} name={title} dot={{ r: 2 }} strokeWidth={2} />
                    </LineChart>
                  ) : (
                    <BarChart data={data}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="value" fill={LINE_COLORS[i % LINE_COLORS.length]} />
                    </BarChart>
                  )}
                </ResponsiveContainer>
              </div>
            )
          })}
        </div>
      )
    }
    let data: { name: string; value?: number; [k: string]: unknown }[]
    if (p.multi_series && Array.isArray(p.data) && p.data.length > 0) {
      data = p.data as { name: string; [k: string]: unknown }[]
    } else if (p.data && !Array.isArray(p.data) && 'x' in (p.data as object)) {
      const d = p.data as { x?: string[]; y?: number[] }
      data = (d.x || []).map((x, i) => ({ name: x, value: (d.y || [])[i] ?? 0 }))
    } else {
      data = (p.labels || []).map((l, i) => ({ name: l, value: (p.values || [])[i] ?? 0 }))
    }
    if (data.length === 0) return null
    const seriesKeys = p.multi_series
      ? [...new Set(data.flatMap((row) => Object.keys(row).filter((k) => k !== 'name')))].filter(Boolean)
      : (data[0] ? Object.keys(data[0]).filter((k) => k !== 'name') : [])
    return (
      <div className="gen-ui-chart">
        {genUi.type === 'line' ? (
          <ResponsiveContainer width="100%" height={200}>
            {seriesKeys.length > 1 ? (
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend />
                {seriesKeys.map((key, i) => (
                  <Line key={key} type="monotone" dataKey={key} stroke={LINE_COLORS[i % LINE_COLORS.length]} name={p.series_labels?.[key] ?? key} connectNulls isAnimationActive={false} strokeWidth={2} dot={false} />
                ))}
              </LineChart>
            ) : (
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                {seriesKeys.length > 0 ? (
                  <>
                    {seriesKeys.map((key, i) => (
                      <Line key={key} type="monotone" dataKey={key} stroke={LINE_COLORS[i % LINE_COLORS.length]} name={p.series_labels?.[key] ?? key} connectNulls dot={{ r: 2 }} isAnimationActive={false} strokeWidth={2} />
                    ))}
                    <Legend />
                  </>
                ) : (
                  <Line type="monotone" dataKey="value" stroke="#3b82f6" dot={{ r: 2 }} isAnimationActive={false} strokeWidth={2} />
                )}
              </LineChart>
            )}
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    )
  }

  const sessionDisplayId = (id: string | null) => id ? id.replace(/^web-/, '').slice(0, 12) : '—'

  const orbListenersRef = useRef<{ onMove: (ev: PointerEvent) => void; cleanup: () => void } | null>(null)

  const handleOrbPointerDown = useCallback((e: React.PointerEvent) => {
    const el = e.currentTarget as HTMLElement
    const pointerId = e.pointerId
    el.setPointerCapture(pointerId)
    orbJustDraggedRef.current = false
    const startPos = orbPos ?? {
      x: window.innerWidth - 24 - 48,
      y: window.innerHeight - 24 - 48
    }
    orbDragRef.current = { startX: e.clientX, startY: e.clientY, startPos }

    const onMove = (ev: PointerEvent) => {
      if (ev.pointerId !== pointerId || !orbDragRef.current) return
      const dx = ev.clientX - orbDragRef.current.startX
      const dy = ev.clientY - orbDragRef.current.startY
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) orbJustDraggedRef.current = true
      const nx = orbDragRef.current.startPos.x + dx
      const ny = orbDragRef.current.startPos.y + dy
      const clampedX = Math.max(0, Math.min(window.innerWidth - 48, nx))
      const clampedY = Math.max(0, Math.min(window.innerHeight - 48, ny))
      setOrbPos({ x: clampedX, y: clampedY })
    }

    const cleanup = () => {
      try { el.releasePointerCapture(pointerId) } catch (_) {}
      orbDragRef.current = null
      window.removeEventListener('pointermove', onMove)
      orbListenersRef.current = null
    }

    orbListenersRef.current = { onMove, cleanup }
    window.addEventListener('pointermove', onMove)
  }, [orbPos])

  const handleOrbPointerUp = useCallback((_e: React.PointerEvent) => {
    orbListenersRef.current?.cleanup()
  }, [])

  const handleOrbPointerCancel = useCallback((_e: React.PointerEvent) => {
    orbListenersRef.current?.cleanup()
  }, [])

  const handleOrbClick = useCallback(() => {
    if (orbJustDraggedRef.current) {
      orbJustDraggedRef.current = false
      return
    }
    setOrbOpen(o => !o)
  }, [])

  const ORB_RESIZE_MIN = { width: 200, height: 200 }
  const ORB_RESIZE_MAX = { width: 500, height: 600 }

  type ResizeCorner = 'se' | 'sw' | 'ne' | 'nw'
  const handleOrbResizePointerDown = useCallback((corner: ResizeCorner) => (e: React.PointerEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const el = e.currentTarget as HTMLElement
    el.setPointerCapture(e.pointerId)
    orbResizeRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startW: orbPanelSize.width,
      startH: orbPanelSize.height
    }
    const dxMult = corner === 'se' || corner === 'ne' ? 1 : -1
    const dyMult = corner === 'se' || corner === 'sw' ? 1 : -1

    const onMove = (ev: PointerEvent) => {
      if (!orbResizeRef.current) return
      const dx = ev.clientX - orbResizeRef.current.startX
      const dy = ev.clientY - orbResizeRef.current.startY
      const dw = dx * dxMult
      const dh = dy * dyMult
      const w = Math.max(ORB_RESIZE_MIN.width, Math.min(ORB_RESIZE_MAX.width, orbResizeRef.current.startW + dw))
      const h = Math.max(ORB_RESIZE_MIN.height, Math.min(ORB_RESIZE_MAX.height, orbResizeRef.current.startH + dh))
      setOrbPanelSize({ width: w, height: h })
    }

    const onUp = () => {
      el.releasePointerCapture(e.pointerId)
      orbResizeRef.current = null
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }, [orbPanelSize])

  const ORB_PAGE_SIZE = 5
  const ORB_TASK_PAGE_SIZE = 10
  const sessionsPageCount = Math.max(1, Math.ceil(treeRoots.length / ORB_PAGE_SIZE))
  const skillsPageCount = Math.max(1, Math.ceil(skills.length / ORB_PAGE_SIZE))
  const workspacePageCount = Math.max(1, Math.ceil(workspaceFiles.length / ORB_PAGE_SIZE))
  const safeSessionsPage = Math.min(orbSessionsPage, sessionsPageCount - 1)
  const safeSkillsPage = Math.min(orbSkillsPage, skillsPageCount - 1)
  const safeWorkspacePage = Math.min(orbWorkspacePage, workspacePageCount - 1)
  const paginatedRoots = treeRoots.slice(safeSessionsPage * ORB_PAGE_SIZE, (safeSessionsPage + 1) * ORB_PAGE_SIZE)
  const paginatedSkills = skills.slice(safeSkillsPage * ORB_PAGE_SIZE, (safeSkillsPage + 1) * ORB_PAGE_SIZE)
  const paginatedWorkspace = workspaceFiles.slice(safeWorkspacePage * ORB_PAGE_SIZE, (safeWorkspacePage + 1) * ORB_PAGE_SIZE)

  const allChildSessions = treeRoots
    .flatMap(r => r.children || [])
    .slice()
    .sort((a, b) => (b.created_at || 0) - (a.created_at || 0))
  const tasksPageCount = Math.max(1, Math.ceil(allChildSessions.length / ORB_TASK_PAGE_SIZE))
  const safeTasksPage = Math.min(orbTasksPage, tasksPageCount - 1)
  const paginatedTasks = allChildSessions.slice(
    safeTasksPage * ORB_TASK_PAGE_SIZE,
    (safeTasksPage + 1) * ORB_TASK_PAGE_SIZE
  )

  return (
    <div className="app">
      <div className="main">
        <div className="chat-area">
          <div className="chat-session-bar">
            <span className="session-id-label">Session</span>
            <code className="session-id-value">{sessionDisplayId(currentSessionId)}</code>
          </div>
          <div className="chat-container" ref={chatContainerRef} onScroll={onChatScroll}>
          <div className="chat">
            {messages.map((m, i) => (
              <div key={i} className={`message ${m.role}`}>
                {m.skill && <span className="skill-tag">[{m.skill}]</span>}
                {m.role === 'assistant' && (
                  <span className="message-meta">
                    {m.cacheHit !== undefined && (
                      <span className="badge">{m.cacheHit ? 'Cache hit' : 'Live inference'}</span>
                    )}
                    {m.tokens != null && m.tokens > 0 && (
                      <span className="token-badge">{m.tokens} tokens</span>
                    )}
                  </span>
                )}
                {m.genUi && renderGenUi(m.genUi)}
                <div className="message-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                </div>
                {m.role === 'assistant' && m.references && m.references.length > 0 && (
                  <details className="message-references">
                    <summary>References ({m.references.length})</summary>
                    <ul>
                      {m.references.map((ref, j) => (
                        <li key={j}>
                          <a href={ref.url} target="_blank" rel="noopener noreferrer">
                            {ref.title || ref.url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            ))}
            {(loading || sessionStatus === 'queued' || sessionStatus === 'running') && (
              <div className="message assistant">
                <div className="typing">
                  {loading && liveTokens != null ? `... ${liveTokens} tokens` : sessionStatus === 'queued' ? '... Queued' : sessionStatus === 'running' ? '... Running' : '...'}
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          </div>
          {showScrollToBottom && (
            <button type="button" className="btn-scroll-to-bottom" onClick={scrollToBottom} aria-label="Scroll to bottom">
              ↓
            </button>
          )}

          <div className="input-area">
            <div className="input-wrap">
            {showSkillDropdown && (
              <div className="dropdown skill-dropdown">
                <div className="dropdown-title">Select skill</div>
                <div className="dropdown-options">
                  <button onClick={() => { setSelectedSkill(null); setShowSkillDropdown(false); inputRef.current?.focus() }}>
                    auto
                  </button>
                  {skills.map(s => (
                    <button key={s.name} onClick={() => { setSelectedSkill(s); setShowSkillDropdown(false); inputRef.current?.focus() }}>
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
                  onChange={e => setFileQuery(e.target.value)}
                />
                <div className="dropdown-options">
                  {filteredFiles.slice(0, 20).map(f => (
                    <button key={f} onClick={() => {
                      setInput(i => i + (i ? ' ' : '') + `@${f}`)
                      setShowFileDropdown(false)
                      inputRef.current?.focus()
                    }}>
                      {f}
                    </button>
                  ))}
                </div>
              </div>
            )}
              {selectedSkill && <span className="skill-badge">{selectedSkill.name}</span>}
              <input
                ref={inputRef}
                type="text"
                placeholder={selectedSkill ? selectedSkill.description : 'Ask anything · / select skill · @ select file'}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onFocus={() => setInput(i => i)}
                disabled={sendMode === 'sync' && loading}
              />
              <span className="send-mode-toggle" title={sendMode === 'async' ? 'Send in background (input never blocked)' : 'Wait for reply in this chat'}>
                <button type="button" className={sendMode === 'async' ? 'active' : ''} onClick={() => setSendMode('async')}>Background</button>
                <button type="button" className={sendMode === 'sync' ? 'active' : ''} onClick={() => setSendMode('sync')}>Wait</button>
              </span>
              <button type="button" className="btn-send" onClick={sendMessage} disabled={sendMode === 'sync' && loading}>Send</button>
            </div>
          </div>
        </div>

        <div
          className="orb-wrap"
          style={orbPos != null ? { left: orbPos.x, top: orbPos.y, right: 'auto', bottom: 'auto' } : undefined}
        >
          {orbOpen && (
            <div className="orb-backdrop" onClick={() => setOrbOpen(false)} aria-hidden />
          )}
          <div
            className={`orb-panel ${orbOpen ? 'open' : ''}`}
            style={{
              width: orbPanelSize.width,
              height: orbPanelSize.height,
              minWidth: ORB_RESIZE_MIN.width,
              minHeight: ORB_RESIZE_MIN.height,
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            <div className="orb-panel-scroll">
            <div className="orb-panel-header">
              Sophon {currentSessionId && <code className="orb-session-id">{sessionDisplayId(currentSessionId)}</code>}
            </div>
            <h3 className="orb-section">Sessions</h3>
            <div className="orb-tree">
              {paginatedRoots.map(root => (
                <div key={root.id} className="orb-tree-root">
                  <div
                    role="button"
                    tabIndex={0}
                    className={`session-tab ${currentSessionId === root.id ? 'active' : ''}`}
                    onClick={() => switchToSession(root.id)}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); switchToSession(root.id) } }}
                  >
                    <span className="session-tab-label">{root.id.replace(/^web-/, '').slice(0, 8)}{(root.message_count ?? 0) > 0 ? ` (${root.message_count})` : ''}</span>
                    <button type="button" className="session-tab-delete" onClick={e => { e.stopPropagation(); handleDeleteSession(root.id, e) }} aria-label="Delete">×</button>
                  </div>
                  {root.children.length > 0 && (
                    <div className="orb-tree-children">
                      {root.children.map(c => (
                        <div
                          key={c.session_id}
                          role="button"
                          tabIndex={0}
                          className={`orb-tree-child status-${c.status} ${currentSessionId === c.session_id ? 'active' : ''}`}
                          onClick={() => switchToSession(c.session_id)}
                          onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); switchToSession(c.session_id) } }}
                        >
                          <span className="orb-tree-child-title">{c.title || c.session_id.replace(/^web-/, '').slice(0, 8)}</span>
                          <span className={`orb-tree-child-status status-${c.status}`}>{c.status}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
            {sessionsPageCount > 1 && (
              <div className="orb-pagination">
                <button type="button" disabled={safeSessionsPage === 0} onClick={() => setOrbSessionsPage(p => Math.max(0, p - 1))}>‹</button>
                <span>{safeSessionsPage + 1}/{sessionsPageCount}</span>
                <button type="button" disabled={safeSessionsPage >= sessionsPageCount - 1} onClick={() => setOrbSessionsPage(p => Math.min(sessionsPageCount - 1, p + 1))}>›</button>
              </div>
            )}
            <div className="session-actions">
              <button className="btn-new-session" onClick={() => { handleNewSession(); setOrbOpen(false) }}>+ New chat</button>
              {currentSessionId && (
                <button className="btn-fork" onClick={() => { handleForkSession(); setOrbOpen(false) }}>Fork</button>
              )}
            </div>
            {allChildSessions.length > 0 && (
              <>
                <h3 className="orb-section">Recent tasks</h3>
                <div className="orb-tree">
                  {paginatedTasks.map(task => (
                    <div
                      key={task.session_id}
                      role="button"
                      tabIndex={0}
                      className={`orb-tree-child status-${task.status} ${currentSessionId === task.session_id ? 'active' : ''}`}
                      onClick={() => switchToSession(task.session_id)}
                      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); switchToSession(task.session_id) } }}
                    >
                      <span className="orb-tree-child-title">
                        {task.title || task.session_id.replace(/^web-/, '').slice(0, 8)}
                      </span>
                      <span className={`orb-tree-child-status status-${task.status}`}>{task.status}</span>
                    </div>
                  ))}
                </div>
                {tasksPageCount > 1 && (
                  <div className="orb-pagination">
                    <button
                      type="button"
                      disabled={safeTasksPage === 0}
                      onClick={() => setOrbTasksPage(p => Math.max(0, p - 1))}
                    >
                      ‹
                    </button>
                    <span>{safeTasksPage + 1}/{tasksPageCount}</span>
                    <button
                      type="button"
                      disabled={safeTasksPage >= tasksPageCount - 1}
                      onClick={() => setOrbTasksPage(p => Math.min(tasksPageCount - 1, p + 1))}
                    >
                      ›
                    </button>
                  </div>
                )}
              </>
            )}
            <h3 className="orb-section">Skills</h3>
            <ul>
              {paginatedSkills.map(s => (
                <li key={s.name}>
                  <button
                    type="button"
                    className={`skill-btn ${selectedSkill?.name === s.name ? 'active' : ''}`}
                    onClick={() => { setSelectedSkill(s); setOrbOpen(false) }}
                  >
                    {s.name}
                  </button>
                </li>
              ))}
            </ul>
            {skillsPageCount > 1 && (
              <div className="orb-pagination">
                <button type="button" disabled={safeSkillsPage === 0} onClick={() => setOrbSkillsPage(p => Math.max(0, p - 1))}>‹</button>
                <span>{safeSkillsPage + 1}/{skillsPageCount}</span>
                <button type="button" disabled={safeSkillsPage >= skillsPageCount - 1} onClick={() => setOrbSkillsPage(p => Math.min(skillsPageCount - 1, p + 1))}>›</button>
              </div>
            )}
            <h3 className="orb-section">Workspace</h3>
            <ul className="file-list">
              {paginatedWorkspace.map(f => (
                <li key={f}>{f}</li>
              ))}
            </ul>
            {workspacePageCount > 1 && (
              <div className="orb-pagination">
                <button type="button" disabled={safeWorkspacePage === 0} onClick={() => setOrbWorkspacePage(p => Math.max(0, p - 1))}>‹</button>
                <span>{safeWorkspacePage + 1}/{workspacePageCount}</span>
                <button type="button" disabled={safeWorkspacePage >= workspacePageCount - 1} onClick={() => setOrbWorkspacePage(p => Math.min(workspacePageCount - 1, p + 1))}>›</button>
              </div>
            )}
            <p className="guide">/ select skill · @ select file</p>
            </div>
            <div className="orb-resize-handle orb-resize-se" onPointerDown={handleOrbResizePointerDown('se')} role="separator" aria-label="Resize panel (bottom-right)" />
            <div className="orb-resize-handle orb-resize-sw" onPointerDown={handleOrbResizePointerDown('sw')} role="separator" aria-label="Resize panel (bottom-left)" />
            <div className="orb-resize-handle orb-resize-ne" onPointerDown={handleOrbResizePointerDown('ne')} role="separator" aria-label="Resize panel (top-right)" />
            <div className="orb-resize-handle orb-resize-nw" onPointerDown={handleOrbResizePointerDown('nw')} role="separator" aria-label="Resize panel (top-left)" />
          </div>
          <button
            type="button"
            className={`orb-ball ${orbOpen ? 'open' : ''}`}
            onPointerDown={handleOrbPointerDown}
            onPointerUp={handleOrbPointerUp}
            onPointerCancel={handleOrbPointerCancel}
            onClick={handleOrbClick}
            aria-label={orbOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={orbOpen}
          >
            <span className="orb-icon">{orbOpen ? '×' : '◉'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
