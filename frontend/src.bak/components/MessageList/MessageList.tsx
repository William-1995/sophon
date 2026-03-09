/**
 * MessageList - chat messages + typing indicator.
 */

import { Message } from '../Message/Message'
import type { Message as MessageType } from '../../types'

interface MessageListProps {
  messages: MessageType[]
  loading: boolean
  sessionStatus: string | null
  liveTokens: number | null
  chatEndRef: React.RefObject<HTMLDivElement | null>
}

export function MessageList({
  messages,
  loading,
  sessionStatus,
  liveTokens,
  chatEndRef,
}: MessageListProps) {
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
    <div className="chat">
        {messages.map((m, i) => (
          <Message key={i} message={m} />
        ))}
        {showTyping && (
          <div className="message assistant">
            <div className="typing">{typingText}</div>
          </div>
        )}
        <div ref={chatEndRef} />
    </div>
  )
}
