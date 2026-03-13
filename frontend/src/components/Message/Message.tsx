/**
 * Message - single chat message, WeChat-style layout with avatars.
 * Left: Sophon (sophon.jpeg). Right: User (me.jpeg).
 */

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { API_BASE } from '../../constants'
import { GenUiChart } from '../GenUiChart/GenUiChart'
import type { Message as MessageType } from '../../types'

function formatMessageDate(ts: number): string {
  return new Date(ts).toLocaleDateString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

const USER_IMAGE_URL = `${API_BASE || ''}/api/workspace/profile-image`
const SOPHON_IMAGE_URL = `${API_BASE || ''}/api/workspace/sophon-image`

function UserAvatar() {
  const [failed, setFailed] = useState(false)
  return (
    <div className="message-avatar message-avatar-user">
      {failed ? (
        <svg viewBox="0 0 24 24" fill="currentColor" className="avatar-icon">
          <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
        </svg>
      ) : (
        <img
          src={USER_IMAGE_URL}
          alt="User"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  )
}

export function SophonAvatar() {
  const [failed, setFailed] = useState(false)
  return (
    <div className="message-avatar message-avatar-sophon">
      {failed ? (
        <div className="avatar-fallback">S</div>
      ) : (
        <img
          src={SOPHON_IMAGE_URL}
          alt="Sophon"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  )
}

interface MessageProps {
  message: MessageType
}

export function Message({ message }: MessageProps) {
  const { role, content, skill, cacheHit, tokens, genUi, references, timestamp } = message

  return (
    <div className={`message-row message-row-${role}`}>
      {role === 'assistant' && <SophonAvatar />}
      <div className={`message ${role}`}>
      {timestamp != null && (
        <time className="message-date" dateTime={new Date(timestamp).toISOString().slice(0, 10)}>
          {formatMessageDate(timestamp)}
        </time>
      )}
      {skill && <span className="skill-tag">[{skill}]</span>}
      {role === 'assistant' && (
        <span className="message-meta">
          {cacheHit !== undefined && (
            <span className="badge">{cacheHit ? 'Cache hit' : 'Live inference'}</span>
          )}
          {tokens != null && tokens > 0 && (
            <span className="token-badge">{tokens} tokens</span>
          )}
        </span>
      )}
      {genUi && <GenUiChart genUi={genUi} />}
      <div className="message-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
      {role === 'assistant' && references && references.length > 0 && (
        <details className="message-references">
          <summary>References ({references.length})</summary>
          <ul>
            {references.map((ref, j) => (
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
      {role === 'user' && <UserAvatar />}
    </div>
  )
}
