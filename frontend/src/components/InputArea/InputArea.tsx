/**
 * InputArea - text input, skill/file dropdowns, send mode, send button, voice input.
 * Real-time captions (Web Speech API when available), emotion-colored pulse.
 */

import { useState, useEffect, useRef } from 'react'
import { fetchSpeechStatus, transcribeAudio } from '../../api/resources'
import { EMOTION_RING_COLORS, EMOTION_RING_DEFAULT } from '../../constants'
import type { Skill } from '../../types'

interface InputAreaProps {
  latestEmotion?: string | null
  input: string
  setInput: React.Dispatch<React.SetStateAction<string>>
  selectedSkill: Skill | null
  setSelectedSkill: React.Dispatch<React.SetStateAction<Skill | null>>
  skills: Skill[]
  workspaceFiles: string[]
  showSkillDropdown: boolean
  setShowSkillDropdown: React.Dispatch<React.SetStateAction<boolean>>
  showFileDropdown: boolean
  setShowFileDropdown: React.Dispatch<React.SetStateAction<boolean>>
  fileQuery: string
  setFileQuery: React.Dispatch<React.SetStateAction<string>>
  sendMode: 'async' | 'sync'
  setSendMode: React.Dispatch<React.SetStateAction<'async' | 'sync'>>
  allowBackground?: boolean
  loading: boolean
  runId?: string | null
  onSend: () => void
  onCancel?: () => void
  onResume?: () => void
  lastCancelledRunId?: string | null
  onKeyDown: (e: React.KeyboardEvent) => void
  inputRef: React.RefObject<HTMLInputElement | null>
}

const FILE_FILTER_LIMIT = 20

// Web Speech API (Chrome/Edge) - optional, fallback to MediaRecorder
const SpeechRecognitionAPI =
  typeof window !== 'undefined'
    ? (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionLike; webkitSpeechRecognition?: new () => SpeechRecognitionLike }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognitionLike }).webkitSpeechRecognition
    : undefined

interface SpeechRecognitionLike {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onresult: ((e: { resultIndex: number; results: SpeechRecognitionResultLike[] }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
}
interface SpeechRecognitionResultLike {
  isFinal: boolean
  length: number
  0?: { transcript: string }
}

export function InputArea({
  latestEmotion,
  input,
  setInput,
  selectedSkill,
  setSelectedSkill,
  skills,
  workspaceFiles,
  showSkillDropdown,
  setShowSkillDropdown,
  showFileDropdown,
  setShowFileDropdown,
  fileQuery,
  setFileQuery,
  sendMode,
  setSendMode,
  allowBackground = true,
  loading,
  onSend,
  onCancel,
  onResume,
  lastCancelledRunId,
  runId,
  onKeyDown,
  inputRef,
}: InputAreaProps) {
  const [speechEnabled, setSpeechEnabled] = useState(false)
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [liveTranscript, setLiveTranscript] = useState('')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const transcriptRef = useRef('')

  useEffect(() => {
    fetchSpeechStatus().then((r) => setSpeechEnabled(r.enabled)).catch(() => {})
  }, [])

  const getPulseColor = () => {
    if (!latestEmotion) return undefined
    const c = EMOTION_RING_COLORS[latestEmotion.toLowerCase()]
    return c ?? (latestEmotion ? EMOTION_RING_DEFAULT : undefined)
  }

  const stopRecording = useRef<(() => void) | null>(null)

  const toggleRecord = async () => {
    if (transcribing) return
    if (recording) {
      stopRecording.current?.()
      return
    }
    setLiveTranscript('')
    try {
      if (SpeechRecognitionAPI) {
        const recognition = new SpeechRecognitionAPI()
        recognition.continuous = true
        recognition.interimResults = true
        recognition.lang = 'zh-CN'
        transcriptRef.current = ''
        recognition.onresult = (e: { resultIndex: number; results: SpeechRecognitionResultLike[] }) => {
          let finalText = transcriptRef.current
          let interim = ''
          for (let i = e.resultIndex; i < e.results.length; i++) {
            const r = e.results[i]
            const t = (r as { 0?: { transcript: string } })[0]?.transcript ?? ''
            if (r.isFinal) finalText += t
            else interim = t
          }
          transcriptRef.current = finalText
          setLiveTranscript(finalText + (interim ? ` ${interim}` : ''))
        }
        recognition.onend = () => {
          setRecording(false)
          recognitionRef.current = null
          const text = transcriptRef.current.trim()
          if (text) setInput((i) => i + (i ? ' ' : '') + text)
          setLiveTranscript('')
        }
        recognition.onerror = () => {
          setRecording(false)
          setLiveTranscript('')
        }
        recognitionRef.current = recognition
        recognition.start()
        setRecording(true)
        stopRecording.current = () => {
          recognition.stop()
        }
      } else {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const rec = new MediaRecorder(stream)
        chunksRef.current = []
        rec.ondataavailable = (e) => {
          if (e.data.size) chunksRef.current.push(e.data)
        }
        rec.onstop = async () => {
          setRecording(false)
          mediaRecorderRef.current = null
          stream.getTracks().forEach((t) => t.stop())
          if (chunksRef.current.length === 0) {
            setLiveTranscript('')
            return
          }
          setTranscribing(true)
          setLiveTranscript('Transcribing...')
          try {
            const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
            const { text } = await transcribeAudio(blob)
            if (text) setInput((i) => i + (i ? ' ' : '') + text)
          } catch (e) {
            console.error('Transcribe failed:', e)
          } finally {
            setTranscribing(false)
            setLiveTranscript('')
          }
        }
        mediaRecorderRef.current = rec
        rec.start()
        setRecording(true)
        setLiveTranscript('Listening...')
        stopRecording.current = () => {
          rec.stop()
        }
      }
    } catch (e) {
      console.error('Mic access failed:', e)
      setRecording(false)
      setLiveTranscript('')
    }
  }

  useEffect(() => {
    return () => {
      stopRecording.current?.()
    }
  }, [])

  const filteredFiles = fileQuery
    ? workspaceFiles.filter((f) =>
        f.toLowerCase().includes(fileQuery.toLowerCase())
      )
    : workspaceFiles

  const selectSkill = (skill: Skill | null) => {
    setSelectedSkill(skill)
    setShowSkillDropdown(false)
    inputRef.current?.focus()
  }

  const selectFile = (path: string) => {
    setInput((i) => i + (i ? ' ' : '') + `@${path}`)
    setShowFileDropdown(false)
    inputRef.current?.focus()
  }

  const pulseColor = getPulseColor()

  return (
    <div className="input-area">
      {(recording || transcribing) && liveTranscript && (
        <div className="voice-caption" role="status">
          <span className="voice-caption-text">{liveTranscript}</span>
        </div>
      )}
      <div className="input-wrap">
        {showSkillDropdown && (
          <div className="dropdown skill-dropdown">
            <div className="dropdown-title">Select skill</div>
            <div className="dropdown-options">
              <button onClick={() => selectSkill(null)}>auto</button>
              {skills.map((s) => (
                <button key={s.name} onClick={() => selectSkill(s)}>
                  {s.name}
                </button>
              ))}
            </div>
          </div>
        )}
        {showFileDropdown && (
          <div className="dropdown file-dropdown">
            <div className="dropdown-title">Select file (@ path)</div>
            <input
              type="text"
              placeholder="Filter..."
              value={fileQuery}
              onChange={(e) => setFileQuery(e.target.value)}
            />
            <div className="dropdown-options">
              {filteredFiles.slice(0, FILE_FILTER_LIMIT).map((f) => (
                <button key={f} onClick={() => selectFile(f)}>
                  {f}
                </button>
              ))}
            </div>
          </div>
        )}
        {selectedSkill && (
          <span className="skill-badge">{selectedSkill.name}</span>
        )}
        <input
          ref={inputRef}
          type="text"
          placeholder={
            selectedSkill
              ? selectedSkill.description
              : 'Ask anything · / select skill · @ select file'
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => setInput((i) => i)}
          disabled={(!allowBackground || sendMode === 'sync') && loading}
        />
        {allowBackground && (
          <span
            className="send-mode-toggle"
            title={
              sendMode === 'async'
                ? 'Send in background (input never blocked)'
                : 'Wait for reply in this chat'
            }
          >
            <button
              type="button"
              className={sendMode === 'async' ? 'active' : ''}
              onClick={() => setSendMode('async')}
            >
              Background
            </button>
            <button
              type="button"
              className={sendMode === 'sync' ? 'active' : ''}
              onClick={() => setSendMode('sync')}
            >
              Wait
            </button>
          </span>
        )}
        {loading && runId && sendMode === 'sync' && onCancel ? (
          <button
            type="button"
            className="btn-cancel"
            onClick={onCancel}
            title="Cancel run"
          >
            Cancel
          </button>
        ) : lastCancelledRunId && !loading && onResume ? (
          <button
            type="button"
            className="btn-resume"
            onClick={onResume}
            title="Resume from checkpoint"
          >
            Resume
          </button>
        ) : (
          <>
            {speechEnabled && (
              <button
                type="button"
                className={`btn-mic ${recording ? 'recording' : ''} ${pulseColor ? 'btn-mic-emotion' : ''}`}
                style={
                  pulseColor && recording
                    ? ({ '--mic-pulse-color': pulseColor } as React.CSSProperties)
                    : undefined
                }
                onClick={toggleRecord}
                disabled={transcribing}
                title={recording ? 'Stop recording' : 'Voice input'}
                aria-label={recording ? 'Stop recording' : 'Voice input'}
              >
                {recording ? (
                  <span className="btn-mic-waves" aria-hidden>
                    <svg viewBox="0 0 24 24" fill="currentColor">
                      <rect x="6" y="8" width="2" height="8" rx="1" className="bar bar-1" />
                      <rect x="11" y="4" width="2" height="16" rx="1" className="bar bar-2" />
                      <rect x="16" y="8" width="2" height="8" rx="1" className="bar bar-3" />
                    </svg>
                  </span>
                ) : (
                  <span className="btn-mic-icon" aria-hidden>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z" />
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                      <line x1="12" y1="19" x2="12" y2="22" />
                    </svg>
                  </span>
                )}
              </button>
            )}
            <button
              type="button"
              className="btn-send"
              onClick={onSend}
              disabled={(!allowBackground || sendMode === 'sync') && loading}
              title="Send"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20">
                <path d="M12 19V5M5 12l7-7 7 7" />
              </svg>
            </button>
          </>
        )}
      </div>
    </div>
  )
}
