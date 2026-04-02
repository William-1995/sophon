/**
 * MessageList - chat messages + typing indicator + real-time LLM events.
 */

import React from 'react'
import { Message, SophonAvatar } from '../Message/Message'
import type { Message as MessageType } from '../../types'
import type { InvestigationReport } from '../../hooks/useChat'

interface LiveEvent {
  type: string
  [key: string]: unknown
}

interface MessageListProps {
  messages: MessageType[]
  loading: boolean
  sessionStatus: string | null
  liveTokens: number | null
  liveEvents?: LiveEvent[]
  liveTodos?: { id: string; title: string; status: string }[]
  liveThinking?: string[]
  investigationReport?: InvestigationReport | null
  chatEndRef: React.RefObject<HTMLDivElement | null>
}

/** Fallback labels when backend display_text is not available. Same wording as backend _FRIENDLY_LABELS. */
const SKILL_LABELS: Record<string, string> = {
  'task_plan': 'Drafting a step-by-step plan for your approval',
  'deep-research': 'Researching your topic: breaking down the question, searching sources, drafting the report',
  'search': 'Searching the web for relevant information',
  'crawler': 'Fetching and reading the webpage',
  'filesystem': 'Reading or writing files',
  'troubleshoot': 'Analyzing logs and traces to diagnose the issue',
  'memory': 'Looking up past conversations',
  'capabilities': 'Listing available capabilities',
  'excel': 'Processing the workbook',
  'time': 'Getting current time',
  'log-analyze': 'Analyzing log files',
  'trace': 'Inspecting trace data',
  'metrics': 'Fetching metrics',
}

function formatEvent(evt: LiveEvent): string {
  const t = evt.type || 'event'
  // Support both snake_case (backend) and camelCase (AG-UI serialization)
  const displayText = (evt.display_text ?? evt.displayText) as string | undefined
  const desc = evt.description as string | undefined
  if (displayText) return String(displayText)
  if (desc) {
    const d = String(desc)
    return d.length > 80 ? d.slice(0, 80) + '...' : d
  }
  if (t === 'PROGRESS') {
    if (evt.current != null && evt.total != null && evt.message)
      return String(evt.message)
    if (evt.current != null && evt.total != null)
      return `Progress: ${evt.current}/${evt.total}`
    if (evt.query) return `Searching: ${String(evt.query).slice(0, 50)}`
    if (evt.url) return `Crawling: ${String(evt.url).slice(0, 60)}`
  }
  if (t === 'THINKING' && evt.content)
    return `Thinking: ${String(evt.content).slice(0, 60)}...`
  if (t === 'INVESTIGATION_REPORT') {
    const payload = (evt.payload && typeof evt.payload === 'object') ? (evt.payload as Record<string, unknown>) : evt
    const nextAction = String(payload.recommended_next_action ?? '')
    const missing = Array.isArray(payload.inputs_missing) ? payload.inputs_missing.map(String).join(', ') : ''
    const tools = Array.isArray(payload.usable_tools) ? payload.usable_tools.map(String).join(', ') : ''
    const parts = ['Investigation report']
    if (missing) parts.push(`Missing: ${missing}`)
    if (tools) parts.push(`Tools: ${tools}`)
    if (nextAction) parts.push(`Next: ${nextAction}`)
    return parts.join(' • ')
  }
  if (t === 'DECISION_REQUIRED') return 'Decision required'
  if (t === 'TOOL_START' && evt.skill) {
    const label = SKILL_LABELS[String(evt.skill)]
    if (label) return label
  }
  if (evt.phase) return `${t}: ${evt.phase}`
  if (evt.skill && evt.action) return `${evt.skill}.${evt.action}`
  if (evt.tool) return `${t}: ${evt.tool}`
  if (evt.message) return `${t}: ${String(evt.message).slice(0, 60)}`
  return t
}

function todoStatusIcon(status: string): string {
  if (status === 'done') return '✓'
  if (status === 'in_progress') return '●'
  return '○'
}

function formatInvestigationSummary(report: InvestigationReport | null): string[] {
  if (!report) return []
  const lines: string[] = []
  if (report.intent) lines.push(`Intent: ${report.intent}`)
  if (report.inputs_found?.length) lines.push(`Found: ${report.inputs_found.join(', ')}`)
  if (report.inputs_missing?.length) lines.push(`Missing: ${report.inputs_missing.join(', ')}`)
  if (report.candidate_files?.length) lines.push(`Candidates: ${report.candidate_files.join(', ')}`)
  if (report.usable_tools?.length) lines.push(`Tools: ${report.usable_tools.join(', ')}`)
  if (report.recommended_next_action) lines.push(`Next: ${report.recommended_next_action}`)
  return lines
}

export function MessageList({
  messages,
  loading,
  sessionStatus,
  liveTokens,
  liveEvents = [],
  liveTodos = [],
  liveThinking = [],
  investigationReport = null,
  chatEndRef,
}: MessageListProps) {
  const [eventsExpanded, setEventsExpanded] = React.useState(false)
  const showTyping =
    loading || sessionStatus === 'queued' || sessionStatus === 'running'
  const typingText = loading && liveTokens != null
    ? `... ${liveTokens} tokens`
    : sessionStatus === 'queued'
      ? '... Queued'
      : sessionStatus === 'running'
        ? '... Running'
        : '...'

  return (
    <div className="chat-content-max">
      <div className="chat">
        {messages.map((m, i) => (
          <Message key={i} message={m} />
        ))}
        {showTyping && (
          <div className="message-row message-row-assistant">
            <SophonAvatar />
            <div className="message assistant">
              <div className="typing">{typingText}</div>
              {(liveThinking.length > 0 || investigationReport) && (
                <details className="live-thinking" open={eventsExpanded}>
                  <summary>Thinking</summary>
                  <ul>
                    {liveThinking.map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                    {formatInvestigationSummary(investigationReport).map((line, i) => (
                      <li key={`report-${i}`}>{line}</li>
                    ))}
                  </ul>
                </details>
              )}
              {liveTodos.length > 0 && (
                <details
                  className="live-todos"
                  open={eventsExpanded}
                  onToggle={(e) => setEventsExpanded((e.target as HTMLDetailsElement).open)}
                >
                  <summary>Plan ({liveTodos.length} steps)</summary>
                  <ul>
                    {liveTodos.map((t) => (
                      <li key={t.id} className={`todo-status-${t.status}`}>
                        {todoStatusIcon(t.status)} {t.title}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {liveEvents.length > 0 && (
                <details
                  className="live-events"
                  open={eventsExpanded}
                  onToggle={(e) => setEventsExpanded((e.target as HTMLDetailsElement).open)}
                >
                  <summary>Current tasks ({liveEvents.length})</summary>
                  <ul>
                    {liveEvents.map((evt, i) => (
                      <li key={i}>{formatEvent(evt)}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>
    </div>
  )
}
