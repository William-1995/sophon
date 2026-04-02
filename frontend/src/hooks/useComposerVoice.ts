/**
 * Shared voice input for Chat + Workflow composers: Web Speech with interim
 * caption, MediaRecorder + server STT fallback — matches InputArea behavior.
 */

import { useState, useEffect, useRef, type Dispatch, type SetStateAction } from 'react'
import { fetchSpeechStatus, transcribeAudio } from '../api/resources'

const SpeechRecognitionAPI =
  typeof window !== 'undefined'
    ? (
        window as unknown as {
          SpeechRecognition?: new () => SpeechRecognitionLike
          webkitSpeechRecognition?: new () => SpeechRecognitionLike
        }
      ).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognitionLike })
        .webkitSpeechRecognition
    : undefined

interface SpeechRecognitionLike {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onresult:
    | ((e: { resultIndex: number; results: SpeechRecognitionResultLike[] }) => void)
    | null
  onend: (() => void) | null
  onerror: (() => void) | null
}

interface SpeechRecognitionResultLike {
  isFinal: boolean
  length: number
  0?: { transcript: string }
}

export function useComposerVoice(setField: Dispatch<SetStateAction<string>>) {
  const [serverSpeechEnabled, setServerSpeechEnabled] = useState(true)
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [liveTranscript, setLiveTranscript] = useState('')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const transcriptRef = useRef('')
  const stopRecording = useRef<(() => void) | null>(null)

  useEffect(() => {
    fetchSpeechStatus()
      .then((r) => setServerSpeechEnabled(r.enabled))
      .catch(() => setServerSpeechEnabled(true))
  }, [])

  const hasBrowserSpeech = Boolean(SpeechRecognitionAPI)
  const voiceCapable = hasBrowserSpeech || serverSpeechEnabled

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
        recognition.onresult = (e: {
          resultIndex: number
          results: SpeechRecognitionResultLike[]
        }) => {
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
          if (text) setField((i) => i + (i ? ' ' : '') + text)
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
            if (text) setField((i) => i + (i ? ' ' : '') + text)
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

  return {
    recording,
    transcribing,
    liveTranscript,
    voiceCapable,
    toggleRecord,
  }
}
