import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AudioMutedOutlined, AudioOutlined, PhoneFilled } from '@ant-design/icons'
import { App, Button, Flex, Modal, Tooltip, Typography } from 'antd'
import { callsApi } from '../api'
import { desktopNotify } from '../notify'
import { displayName } from '../people'
import { CallContext, formatDuration, useChat } from '../team'
import { PersonAvatar } from './People'

const POLL_MS = 1000
const FINISHED = ['ended', 'missed', 'declined', 'cancelled']
const END_TEXT = {
  ended: 'Call ended',
  missed: 'No answer',
  declined: 'Call declined',
  cancelled: 'Call cancelled',
}

// A simple ringtone (incoming) or ringback (outgoing) made with the Web Audio API.
function startTone(kind) {
  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) return () => {}
  const ctx = new Ctx()
  const gain = ctx.createGain()
  gain.gain.value = 0
  gain.connect(ctx.destination)
  const osc = ctx.createOscillator()
  osc.frequency.value = kind === 'incoming' ? 660 : 440
  osc.connect(gain)
  osc.start()
  const volume = kind === 'incoming' ? 0.15 : 0.06
  let on = false
  const timer = setInterval(() => {
    on = !on
    gain.gain.setTargetAtTime(on ? volume : 0, ctx.currentTime, 0.02)
  }, kind === 'incoming' ? 700 : 1500)
  return () => {
    clearInterval(timer)
    osc.stop()
    ctx.close().catch(() => {})
  }
}

// Handles one audio call at a time, on every page: ringing, the WebRTC
// connection (audio goes straight between the two browsers), and the call panel.
export function CallProvider({ children }) {
  const { message, modal } = App.useApp()
  const { incomingCall } = useChat()
  const [call, setCall] = useState(null) // { id, peer, incoming, status, phase }
  const [muted, setMuted] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const pc = useRef(null)
  const stream = useRef(null)
  const audio = useRef(null)
  const afterSeq = useRef(0)
  const pendingCandidates = useRef([])
  const offered = useRef(false)
  const connectedAt = useRef(null)
  const iceServers = useRef(null)
  const callRef = useRef(null)
  const dismissedIncoming = useRef(new Set())

  useEffect(() => {
    callRef.current = call
  }, [call])

  const cleanup = useCallback(() => {
    pc.current?.close()
    pc.current = null
    stream.current?.getTracks().forEach((t) => t.stop())
    stream.current = null
    if (audio.current) audio.current.srcObject = null
    pendingCandidates.current = []
    offered.current = false
    afterSeq.current = 0
    connectedAt.current = null
    setMuted(false)
    setElapsed(0)
  }, [])

  // text: undefined = the usual message for that status, false = no message.
  const finish = useCallback(
    (status, text) => {
      cleanup()
      setCall(null)
      const shown = text === undefined ? END_TEXT[status] : text
      if (shown) message.info(shown)
    },
    [cleanup, message],
  )

  async function servers() {
    if (!iceServers.current) iceServers.current = (await callsApi.config()).ice_servers
    return iceServers.current
  }

  // Microphone + peer connection. Signals go to the other side through the server.
  const connect = useCallback(async (callId) => {
    stream.current = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    const peer = new RTCPeerConnection({ iceServers: await servers() })
    pc.current = peer
    stream.current.getTracks().forEach((track) => peer.addTrack(track, stream.current))
    peer.onicecandidate = (e) => {
      if (e.candidate) callsApi.signal(callId, 'candidate', e.candidate.toJSON()).catch(() => {})
    }
    peer.ontrack = (e) => {
      if (audio.current) {
        audio.current.srcObject = e.streams[0]
        audio.current.play().catch(() => {})
      }
    }
    peer.onconnectionstatechange = () => {
      if (peer.connectionState === 'connected') {
        connectedAt.current ??= Date.now()
        setCall((c) => (c ? { ...c, phase: 'connected' } : c))
      } else if (peer.connectionState === 'failed') {
        callsApi.end(callId).catch(() => {})
        finish('ended', "Couldn't connect the call. The network may be blocking it.")
      }
    }
    return peer
  }, [finish])

  const applySignal = useCallback(async (callId, signal) => {
    const peer = pc.current
    if (!peer) return
    if (signal.kind === 'offer') {
      await peer.setRemoteDescription(signal.data)
      const answer = await peer.createAnswer()
      await peer.setLocalDescription(answer)
      await callsApi.signal(callId, 'answer', { type: answer.type, sdp: answer.sdp })
    } else if (signal.kind === 'answer') {
      await peer.setRemoteDescription(signal.data)
    } else if (signal.kind === 'candidate') {
      if (peer.remoteDescription) await peer.addIceCandidate(signal.data).catch(() => {})
      else pendingCandidates.current.push(signal.data)
      return
    }
    for (const c of pendingCandidates.current.splice(0)) await peer.addIceCandidate(c).catch(() => {})
  }, [])

  // While a call is open: poll its status and the other side's signals every second.
  const callId = call?.id
  useEffect(() => {
    if (!callId) return
    let stopped = false
    let timer
    const tick = async () => {
      try {
        const res = await callsApi.get(callId, afterSeq.current)
        if (stopped) return
        const current = callRef.current
        if (FINISHED.includes(res.call.status)) {
          finish(res.call.status)
          return
        }
        if (res.call.status === 'active' && current && !current.incoming && !offered.current) {
          // They picked up: set up the connection and send the offer.
          offered.current = true
          setCall((c) => (c ? { ...c, status: 'active', phase: 'connecting' } : c))
          const peer = await connect(callId)
          const offer = await peer.createOffer()
          await peer.setLocalDescription(offer)
          await callsApi.signal(callId, 'offer', { type: offer.type, sdp: offer.sdp })
        }
        for (const signal of res.signals) {
          afterSeq.current = Math.max(afterSeq.current, signal.seq)
          await applySignal(callId, signal)
        }
      } catch (err) {
        if (err?.name === 'NotAllowedError' || err?.name === 'NotFoundError') {
          callsApi.end(callId).catch(() => {})
          finish('ended', 'Allow microphone access in your browser to make calls.')
          return
        }
        // Network hiccup: try again on the next tick.
      }
      if (!stopped) timer = setTimeout(tick, POLL_MS)
    }
    tick()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [callId, connect, finish, applySignal])

  // Call timer.
  useEffect(() => {
    if (call?.phase !== 'connected') return
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - (connectedAt.current ?? Date.now())) / 1000)), 500)
    return () => clearInterval(timer)
  }, [call?.phase])

  // Ringtone / ringback.
  const ringing = call?.status === 'ringing' ? (call.incoming ? 'incoming' : 'outgoing') : null
  useEffect(() => {
    if (!ringing) return
    return startTone(ringing)
  }, [ringing])

  // An incoming call from the app's regular check (only if we're free).
  useEffect(() => {
    if (!incomingCall) {
      // The caller gave up or it timed out before we answered.
      if (callRef.current?.incoming && callRef.current.status === 'ringing') finish('missed', 'Missed call')
      return
    }
    if (callRef.current || dismissedIncoming.current.has(incomingCall.id)) return
    setCall({ id: incomingCall.id, peer: incomingCall.peer, incoming: true, status: 'ringing', phase: 'ringing' })
    if (document.visibilityState !== 'visible') {
      desktopNotify(`${displayName(incomingCall.peer)} is calling`, { body: 'Audio call', tag: `call-${incomingCall.id}` })
    }
  }, [incomingCall, finish])

  const startCall = useCallback(
    async (peer) => {
      if (callRef.current) {
        message.warning('You are already in a call.')
        return
      }
      try {
        const started = await callsApi.start(peer.id)
        setCall({ id: started.id, peer: started.peer, incoming: false, status: 'ringing', phase: 'calling' })
      } catch (err) {
        if (err.status === 409) modal.info({ title: 'Busy', content: err.message })
        else message.error(err.message)
      }
    },
    [message, modal],
  )

  async function accept() {
    const current = callRef.current
    dismissedIncoming.current.add(current.id)
    try {
      await connect(current.id) // ask for the microphone first
      await callsApi.accept(current.id)
      setCall((c) => ({ ...c, status: 'active', phase: 'connecting' }))
    } catch (err) {
      const blocked = err?.name === 'NotAllowedError' || err?.name === 'NotFoundError'
      callsApi.decline(current.id).catch(() => {})
      finish('declined', blocked ? 'Allow microphone access in your browser to take calls.' : err.message)
    }
  }

  async function decline() {
    const current = callRef.current
    dismissedIncoming.current.add(current.id)
    await callsApi.decline(current.id).catch(() => {})
    finish('declined', false)
  }

  async function hangUp() {
    const current = callRef.current
    if (!current) return
    dismissedIncoming.current.add(current.id)
    await callsApi.end(current.id).catch(() => {})
    finish(current.status === 'ringing' ? 'cancelled' : 'ended')
  }

  function toggleMute() {
    const next = !muted
    stream.current?.getAudioTracks().forEach((t) => (t.enabled = !next))
    setMuted(next)
  }

  // Hang up if the tab is closed mid-call (keepalive lets the request finish as the page goes away).
  useEffect(() => {
    const onUnload = () => {
      const current = callRef.current
      if (!current) return
      const csrf = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/)?.[1] ?? ''
      fetch(`/api/calls/${current.id}/end/`, {
        method: 'POST',
        keepalive: true,
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': decodeURIComponent(csrf) },
      }).catch(() => {})
    }
    window.addEventListener('pagehide', onUnload)
    return () => window.removeEventListener('pagehide', onUnload)
  }, [])

  const value = useMemo(() => ({ call, startCall }), [call, startCall])
  const statusText = !call
    ? ''
    : call.phase === 'connected'
      ? formatDuration(elapsed)
      : call.phase === 'connecting'
        ? 'Connecting…'
        : call.incoming
          ? 'Incoming audio call'
          : 'Calling…'

  return (
    <CallContext.Provider value={value}>
      {children}
      <audio ref={audio} autoPlay aria-hidden="true" />
      <Modal
        open={Boolean(call?.incoming && call.status === 'ringing')}
        closable={false}
        mask={{ closable: false }}
        footer={null}
        centered
        width={340}
      >
        {call && (
          <Flex vertical align="center" gap={14} style={{ padding: '12px 0 4px' }}>
            <div className="call-pulse">
              <PersonAvatar person={call.peer} size={84} />
            </div>
            <div style={{ textAlign: 'center' }}>
              <Typography.Title level={4} style={{ margin: 0 }}>
                {displayName(call.peer)}
              </Typography.Title>
              <Typography.Text type="secondary">is calling you · audio</Typography.Text>
            </div>
            <Flex gap={32} style={{ marginTop: 8 }}>
              <Flex vertical align="center" gap={6}>
                <Button
                  shape="circle"
                  size="large"
                  danger
                  type="primary"
                  className="call-btn"
                  icon={<PhoneFilled style={{ transform: 'rotate(135deg)' }} />}
                  onClick={decline}
                  aria-label="Decline"
                />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Decline
                </Typography.Text>
              </Flex>
              <Flex vertical align="center" gap={6}>
                <Button
                  shape="circle"
                  size="large"
                  type="primary"
                  className="call-btn accept"
                  icon={<PhoneFilled />}
                  onClick={accept}
                  aria-label="Accept"
                />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Accept
                </Typography.Text>
              </Flex>
            </Flex>
          </Flex>
        )}
      </Modal>
      {call && !(call.incoming && call.status === 'ringing') && (
        <div className="call-panel" role="dialog" aria-label={`Call with ${displayName(call.peer)}`}>
          <PersonAvatar person={call.peer} size={44} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <Typography.Text strong ellipsis style={{ display: 'block', color: '#fff' }}>
              {displayName(call.peer)}
            </Typography.Text>
            <span className="call-status">{statusText}</span>
          </div>
          <Tooltip title={muted ? 'Unmute' : 'Mute'}>
            <Button
              shape="circle"
              icon={muted ? <AudioMutedOutlined /> : <AudioOutlined />}
              onClick={toggleMute}
              disabled={call.phase !== 'connected' && call.phase !== 'connecting'}
              aria-label={muted ? 'Unmute' : 'Mute'}
              className={muted ? 'call-muted' : ''}
            />
          </Tooltip>
          <Tooltip title={call.status === 'ringing' ? 'Cancel' : 'Hang up'}>
            <Button
              shape="circle"
              danger
              type="primary"
              icon={<PhoneFilled style={{ transform: 'rotate(135deg)' }} />}
              onClick={hangUp}
              aria-label="Hang up"
            />
          </Tooltip>
        </div>
      )}
    </CallContext.Provider>
  )
}
