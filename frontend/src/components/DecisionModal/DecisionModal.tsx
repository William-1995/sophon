/**
 * DecisionModal - HITL dialog when backend emits DECISION_REQUIRED.
 */

import type { DecisionRequired } from '../../api/chat'

interface DecisionModalProps {
  data: DecisionRequired
  onSubmit: (choice: string) => void
  onDismiss?: () => void
}

export function DecisionModal({ data, onSubmit, onDismiss }: DecisionModalProps) {
  const handleSubmit = (choice: string) => {
    onSubmit(choice)
  }

  return (
    <div className="decision-modal-overlay" role="dialog" aria-modal="true">
      <div className="decision-modal">
        <h3>Decision required</h3>
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
}
