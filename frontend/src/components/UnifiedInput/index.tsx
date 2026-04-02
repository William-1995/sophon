import React, { useState, useRef, useCallback, useId } from 'react'
import { AttachmentChips } from '../composer/AttachmentChips'
import { composePlaceholder, createAttachmentId, createStableInputId } from '../composer/composerUtils'

interface FileAttachment {
  file: File
  id: string
}

interface UnifiedInputProps {
  placeholder?: string
  onSubmit: (text: string, attachments: File[]) => void | Promise<void>
  isLoading?: boolean
  disabled?: boolean
}

export const UnifiedInput: React.FC<UnifiedInputProps> = ({
  placeholder = 'Message',
  onSubmit,
  isLoading = false,
  disabled = false,
}) => {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<FileAttachment[]>([])
  const [isRecording, setIsRecording] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const rawId = useId()
  const fileInputId = createStableInputId('workflow-attach', rawId)

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return
    const newFiles = Array.from(files).map((file) => ({ file, id: createAttachmentId() }))
    setAttachments((prev) => [...prev, ...newFiles])
  }, [])

  const handleRemoveAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((att) => att.id !== id))
  }, [])

  const startVoiceInput = () => {
    if (
      !('webkitSpeechRecognition' in window) &&
      !('SpeechRecognition' in window)
    ) {
      alert('Speech recognition is not supported in this browser.')
      return
    }

    const SR =
      (window as unknown as { SpeechRecognition?: new () => WebSpeechRecognition })
        .SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => WebSpeechRecognition })
        .webkitSpeechRecognition
    if (!SR) return
    const recognition = new SR()

    recognition.lang = 'zh-CN'
    recognition.continuous = true
    recognition.interimResults = true

    setIsRecording(true)

    recognition.onresult = (event: WebSpeechResultEvent) => {
      let finalTranscript = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript
        }
      }
      if (finalTranscript) {
        setText((prev) => prev + finalTranscript)
      }
    }

    recognition.onerror = () => {
      setIsRecording(false)
    }

    recognition.onend = () => {
      setIsRecording(false)
    }

    recognition.start()
    ;(window as unknown as { currentRecognition?: WebSpeechRecognition }).currentRecognition =
      recognition
  }

  const stopVoiceInput = () => {
    const w = window as unknown as { currentRecognition?: WebSpeechRecognition }
    w.currentRecognition?.stop()
    setIsRecording(false)
  }

  const handleSubmit = async () => {
    if (!text.trim() && attachments.length === 0) return
    if (isLoading || disabled) return

    await onSubmit(text, attachments.map((att) => att.file))
    setText('')
    setAttachments([])
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSubmit()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    const target = e.target
    target.style.height = 'auto'
    target.style.height = `${Math.min(target.scrollHeight, 220)}px`
  }

  const uploadDisabled = isLoading || disabled

  return (
    <div className="workflow-unified-input">
      <AttachmentChips
        items={attachments.map((att) => ({
          id: att.id,
          name: att.file.name,
          onRemove: () => handleRemoveAttachment(att.id),
          disabled: isLoading,
        }))}
      />

      <div className="input-wrap input-wrap--multiline">
        <div className="input-wrap__leading" aria-label="Attach files">
          <input
            id={fileInputId}
            type="file"
            multiple
            className="file-input-workspace"
            tabIndex={-1}
            onChange={(e) => handleFileSelect(e.target.files)}
            disabled={uploadDisabled}
          />
          <label
            htmlFor={uploadDisabled ? undefined : fileInputId}
            className={`btn-upload hover-tip hover-tip--right${uploadDisabled ? ' btn-upload-disabled' : ''}`}
            data-tooltip="Upload files. They are sent with your description when you press Enter."
            aria-label="Attach files"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              width="20"
              height="20"
              aria-hidden
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </label>
        </div>

        <div className="input-wrap__field">
          <textarea
            ref={textareaRef}
            className="chat-input-field"
            value={text}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={composePlaceholder(placeholder)}
            disabled={isLoading || disabled}
            rows={1}
          />
        </div>

        <div className="input-wrap__trailing" aria-label="Voice input">
          <button
            type="button"
            className={`btn-mic ${isRecording ? 'recording' : ''}`}
            onClick={() =>
              isRecording ? stopVoiceInput() : startVoiceInput()
            }
            disabled={isLoading || disabled}
            title={
              isRecording ? 'Stop recording' : 'Voice input — click to speak'
            }
            aria-label={isRecording ? 'Stop recording' : 'Voice input'}
          >
            {isRecording ? (
              <span className="btn-mic-waves" aria-hidden>
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <rect
                    x="6"
                    y="8"
                    width="2"
                    height="8"
                    rx="1"
                    className="bar bar-1"
                  />
                  <rect
                    x="11"
                    y="4"
                    width="2"
                    height="16"
                    rx="1"
                    className="bar bar-2"
                  />
                  <rect
                    x="16"
                    y="8"
                    width="2"
                    height="8"
                    rx="1"
                    className="bar bar-3"
                  />
                </svg>
              </span>
            ) : (
              <span className="btn-mic-icon" aria-hidden>
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="22" />
                </svg>
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

interface WebSpeechRecognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  onresult: ((e: WebSpeechResultEvent) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
}

interface WebSpeechResultEvent {
  resultIndex: number
  results: Array<{ isFinal: boolean; 0: { transcript: string } }>
}
