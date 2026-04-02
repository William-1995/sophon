import React from 'react'

interface VoiceCaptionProps {
  text?: string | null
}

export function VoiceCaption({ text }: VoiceCaptionProps) {
  if (!text) return null

  return (
    <div className="voice-caption" role="status">
      <span className="voice-caption-text">{text}</span>
    </div>
  )
}
