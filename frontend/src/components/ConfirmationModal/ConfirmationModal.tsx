/**
 * ConfirmationModal - Generic HITL dialog for DECISION_REQUIRED events.
 *
 * Supports payload.files (delete), payload.kind, etc. for extensibility.
 * Rendered via Portal at document.body to avoid clipping.
 */

import { createPortal } from 'react-dom'
import type { ConfirmationRequired } from '../../contexts/ConfirmationContext'

interface ConfirmationModalProps {
  data: ConfirmationRequired
  onSubmit: (choice: string) => void
  onDismiss?: () => void
}

export function ConfirmationModal({ data, onSubmit, onDismiss }: ConfirmationModalProps) {
  const handleSubmit = (choice: string) => {
    onSubmit(choice)
  }

  const files = data.payload?.files

  const modal = (
    <div className="decision-modal-overlay" role="dialog" aria-modal="true">
      <div className="decision-modal">
        <h3>Confirm</h3>
        {files && files.length > 0 && (
          <ul className="decision-file-list">
            {files.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        )}
        {data.message && <p className="decision-message">{data.message}</p>}
        <div className="decision-choices">
          {data.choices?.length ? (
            data.choices.map((c) => (
              <button
                key={c}
                type="button"
                className="btn-decision-choice"
                onClick={() => handleSubmit(c)}
              >
                {c}
              </button>
            ))
          ) : (
            <input
              type="text"
              placeholder="Enter your choice..."
              className="decision-input"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleSubmit((e.target as HTMLInputElement).value)
                }
              }}
            />
          )}
        </div>
        {onDismiss && (
          <button type="button" className="btn-dismiss" onClick={onDismiss}>
            Dismiss
          </button>
        )}
      </div>
    </div>
  )

  return createPortal(modal, document.body)
}
