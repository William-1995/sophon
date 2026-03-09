/**
 * Message - single chat message with markdown, refs, gen_ui, date.
 */

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { GenUiChart } from '../GenUiChart/GenUiChart'
import type { Message as MessageType } from '../../types'

function formatMessageDate(ts: number): string {
  return new Date(ts).toLocaleDateString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

interface MessageProps {
  message: MessageType
}

export function Message({ message }: MessageProps) {
  const { role, content, skill, cacheHit, tokens, genUi, references, timestamp } = message

  return (
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
  )
}
