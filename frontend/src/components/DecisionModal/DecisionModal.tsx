/**
 * DecisionModal - HITL dialog when backend emits DECISION_REQUIRED.
 */

import type { DecisionRequired } from '../../api/chat'

interface InvestigationReportPayload {
  intent?: string
  inputs_missing?: string[]
  candidate_files?: string[]
  [key: string]: unknown
}

interface ClarifyPayload {
  mode?: string
  investigation_report?: InvestigationReportPayload
  [key: string]: unknown
}

interface DecisionModalProps {
  data: DecisionRequired
  onSubmit: (choice: string) => void
  onDismiss?: () => void
}

export function DecisionModal({ data, onSubmit, onDismiss }: DecisionModalProps) {
  const handleSubmit = (choice: string) => {
    onSubmit(choice)
  }

  const hasChoices = Boolean(data.choices?.length)
  const payload = (data as DecisionRequired & { payload?: ClarifyPayload }).payload
  const mode = String(payload?.mode ?? '').toLowerCase()
  const title = mode === 'clarify' || !hasChoices ? 'Need more information' : 'Decision required'
  const placeholder = hasChoices ? 'Enter your choice...' : 'Type the missing detail...'
  const investigation = payload?.investigation_report

  return (
    <div className="decision-modal-overlay" role="dialog" aria-modal="true">
      <div className="decision-modal">
        <h3>{title}</h3>
        {investigation?.intent && (
          <p className="decision-message">
            <strong>Thinking:</strong> {String(investigation.intent)}
          </p>
        )}
        {Array.isArray(investigation?.inputs_missing) && investigation.inputs_missing.length > 0 && (
          <ul className="decision-file-list">
            {(investigation.inputs_missing as string[]).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        {Array.isArray(investigation?.candidate_files) && investigation.candidate_files.length > 0 && (
          <ul className="decision-file-list">
            {(investigation.candidate_files as string[]).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        {data.message && <p className="decision-message">{data.message}</p>}
        <div className="decision-choices">
          {hasChoices ? (
            (data.choices ?? []).map((c) => (
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
              placeholder={placeholder}
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
