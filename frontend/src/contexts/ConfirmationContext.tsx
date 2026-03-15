/**
 * ConfirmationContext - Event-based HITL confirmation.
 *
 * Single source of truth for DECISION_REQUIRED events from:
 * - Sync stream (/api/chat/stream)
 * - Async EventSource (/api/events)
 *
 * Use for delete confirmation, risky actions, or any flow needing user approval.
 */

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react'
import * as chatApi from '../api/chat'

export interface ConfirmationRequired {
  runId: string
  message?: string
  choices?: string[]
  payload?: { files?: string[] }
}

interface ConfirmationContextValue {
  confirmation: ConfirmationRequired | null
  setConfirmation: (data: ConfirmationRequired | null) => void
  submitConfirmation: (choice: string) => Promise<void>
}

const ConfirmationContext = createContext<ConfirmationContextValue | null>(null)

export function ConfirmationProvider({ children }: { children: ReactNode }) {
  const [confirmation, setConfirmation] = useState<ConfirmationRequired | null>(null)

  const submitConfirmation = useCallback(async (choice: string) => {
    if (confirmation?.runId) {
      try {
        await chatApi.submitDecision(confirmation.runId, choice)
        setConfirmation(null)
      } catch {
        // Ignore
      }
    }
  }, [confirmation?.runId])

  const value: ConfirmationContextValue = {
    confirmation,
    setConfirmation,
    submitConfirmation,
  }

  return (
    <ConfirmationContext.Provider value={value}>
      {children}
    </ConfirmationContext.Provider>
  )
}

export function useConfirmation(): ConfirmationContextValue {
  const ctx = useContext(ConfirmationContext)
  if (!ctx) {
    throw new Error('useConfirmation must be used within ConfirmationProvider')
  }
  return ctx
}
