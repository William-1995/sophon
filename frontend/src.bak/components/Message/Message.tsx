/**
 * Message - single chat message with markdown, refs, gen_ui.
 */

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { GenUiChart } from '../GenUiChart/GenUiChart'
import type { Message as MessageType } from '../../types'

interface MessageProps {
  message: MessageType
}

export function Message({ message }: MessageProps) {
  const { role, content, skill, cacheHit, tokens, genUi, references } = message

  return (
    <div className={`message ${role}`}>
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
