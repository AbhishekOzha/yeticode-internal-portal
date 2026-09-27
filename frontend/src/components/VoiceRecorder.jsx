import { useEffect, useRef, useState } from 'react'
import { AudioOutlined, DeleteOutlined, SendOutlined } from '@ant-design/icons'
import { App, Button, Flex, Tooltip, Typography } from 'antd'
import { formatDuration } from '../team'

const MAX_SECONDS = 5 * 60
// Chrome, Edge and Firefox record WebM/Opus; Safari records MP4/AAC.
const TYPES = [
  ['audio/webm;codecs=opus', 'webm'],
  ['audio/webm', 'webm'],
  ['audio/mp4', 'm4a'],
  ['audio/ogg;codecs=opus', 'ogg'],
]

function voiceSupported() {
  return typeof window !== 'undefined' && 'MediaRecorder' in window && Boolean(navigator.mediaDevices?.getUserMedia)
}

// A mic button that records a voice message; while recording it shows a timer,
// a discard button and a send button. Recordings stop at 5 minutes.
export function VoiceRecorder({ onSend, disabled, onRecordingChange, targetName }) {
  const { message } = App.useApp()
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [sending, setSending] = useState(false)
  const recorder = useRef(null)
  const chunks = useRef([])
  const started = useRef(0)
  const keep = useRef(false)
  const format = useRef(TYPES[0])
  const mounted = useRef(false)

  function stopTracks() {
    recorder.current?.stream.getTracks().forEach((t) => t.stop())
  }

  // Release the microphone if the conversation closes mid-recording.
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      keep.current = false
      if (recorder.current?.state === 'recording') recorder.current.stop()
      stopTracks()
    }
  }, [])

  useEffect(() => {
    if (!recording) return
    const timer = setInterval(() => {
      const elapsed = (Date.now() - started.current) / 1000
      setSeconds(elapsed)
      if (elapsed >= MAX_SECONDS && recorder.current?.state === 'recording') {
        keep.current = true
        recorder.current.stop()
      }
    }, 250)
    return () => clearInterval(timer)
  }, [recording])

  useEffect(() => {
    onRecordingChange?.(recording)
  }, [recording, onRecordingChange])

  async function start() {
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      message.error('Allow microphone access in your browser to record a voice message.')
      return
    }
    if (!mounted.current) {
      // The chat changed while the browser was asking for the microphone: don't record into the old one.
      stream.getTracks().forEach((t) => t.stop())
      return
    }
    format.current = TYPES.find(([type]) => MediaRecorder.isTypeSupported(type)) ?? ['', 'webm']
    const rec = new MediaRecorder(stream, format.current[0] ? { mimeType: format.current[0] } : undefined)
    chunks.current = []
    rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    rec.onstop = async () => {
      stopTracks()
      setRecording(false)
      if (!keep.current) return
      const duration = (Date.now() - started.current) / 1000
      const blob = new Blob(chunks.current, { type: rec.mimeType || format.current[0] })
      if (duration < 1 || !blob.size) {
        message.info('That recording was too short.')
        return
      }
      setSending(true)
      try {
        await onSend(blob, duration, format.current[1])
      } finally {
        setSending(false)
      }
    }
    recorder.current = rec
    started.current = Date.now()
    setSeconds(0)
    rec.start(250)
    setRecording(true)
  }

  function finish(send) {
    keep.current = send
    if (recorder.current?.state === 'recording') recorder.current.stop()
  }

  if (!voiceSupported()) return null

  if (!recording) {
    return (
      <Tooltip title="Record a voice message">
        <Button icon={<AudioOutlined />} loading={sending} disabled={disabled} onClick={start} aria-label="Record a voice message" />
      </Tooltip>
    )
  }

  return (
    <Flex align="center" gap={8} className="voice-recording">
      <span className="rec-dot" />
      <Typography.Text strong style={{ fontVariantNumeric: 'tabular-nums' }}>
        {formatDuration(seconds)}
      </Typography.Text>
      {targetName && (
        <Typography.Text type="secondary" ellipsis style={{ flex: 1, minWidth: 0 }}>
          Recording to {targetName}
        </Typography.Text>
      )}
      <Tooltip title="Discard">
        <Button type="text" danger icon={<DeleteOutlined />} onClick={() => finish(false)} aria-label="Discard recording" />
      </Tooltip>
      <Button type="primary" icon={<SendOutlined />} onClick={() => finish(true)} aria-label="Send voice message">
        Send
      </Button>
    </Flex>
  )
}
