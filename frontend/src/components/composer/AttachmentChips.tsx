import React from 'react'

export interface ComposerAttachmentChip {
  id: string
  name: string
  onRemove?: () => void
  disabled?: boolean
}

interface AttachmentChipsProps {
  items: ComposerAttachmentChip[]
  title?: string
  ariaLabel?: string
  className?: string
}

export function AttachmentChips({
  items,
  title = 'Pending attachments',
  ariaLabel = 'Attachments pending send',
  className = '',
}: AttachmentChipsProps) {
  if (items.length === 0) return null

  return (
    <div className={`input-pending-bar ${className}`.trim()} role="region" aria-label={ariaLabel}>
      <div className="input-pending-bar-title">{title}</div>
      <div className="input-pending-chips">
        {items.map((item) => (
          <span key={item.id} className="pending-file-chip">
            <span className="pending-file-name" title={item.name}>
              {item.name}
            </span>
            {item.onRemove && (
              <button
                type="button"
                className="pending-file-remove"
                onClick={item.onRemove}
                disabled={item.disabled}
                aria-label={`Remove ${item.name}`}
              >
                ×
              </button>
            )}
          </span>
        ))}
      </div>
    </div>
  )
}
