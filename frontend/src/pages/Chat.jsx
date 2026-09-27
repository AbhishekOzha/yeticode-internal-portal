import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeftOutlined, PaperClipOutlined, PlusOutlined, SearchOutlined, SendOutlined, SettingOutlined } from '@ant-design/icons'
import { App, Badge, Button, Card, Empty, Flex, Grid, Input, Skeleton, Tooltip, Typography, Upload } from 'antd'
import { teamApi } from '../api'
import { NotificationSwitch } from '../components/NotificationSwitch'
import { ChatAttachment } from '../components/ChatAttachment'
import { GroupAvatar, GroupModal, OnlineAvatar, ReceiptLabel, Ticks } from '../components/ChatBits'
import { PersonAvatar } from '../components/People'
import { VoiceRecorder } from '../components/VoiceRecorder'
import { displayName } from '../people'
import { CHAT_FILE_ACCEPT, MAX_CHAT_FILE_BYTES, messageText, presenceLabel, useChat } from '../team'

const POLL_MS = 3000
const GROUP_GAP_MS = 5 * 60 * 1000

function timeOf(iso) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

function dayOf(iso) {
  const date = new Date(iso)
  const today = new Date()
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1)
  if (date.toDateString() === today.toDateString()) return 'Today'
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return date.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
}

function preview(message, meId) {
  if (!message) return 'No messages yet'
  return `${message.sender === meId ? 'You: ' : ''}${messageText(message)}`
}

function ContactRow({ selected, avatar, name, subtitle, unread, onClick }) {
  return (
    <button type="button" className={`chat-contact ${selected ? 'selected' : ''}`} onClick={onClick}>
      <Badge count={unread} size="small" offset={[-4, 4]}>
        {avatar}
      </Badge>
      <div style={{ minWidth: 0, flex: 1, textAlign: 'left' }}>
        <Flex justify="space-between" gap={8}>
          <Typography.Text strong={unread > 0} ellipsis>
            {name}
          </Typography.Text>
        </Flex>
        <Typography.Text type="secondary" ellipsis style={{ fontSize: 13, display: 'block', fontWeight: unread ? 600 : 400 }}>
          {subtitle}
        </Typography.Text>
      </div>
    </button>
  )
}

// One open conversation: the team room, a colleague (`peer`) or a group.
function Conversation({ me, target, people, onBack, onSent, onManageGroup }) {
  const { message: toast } = App.useApp()
  const { setUnread, presence } = useChat()
  const { peer, group } = target
  const [messages, setMessages] = useState(null)
  const [receipts, setReceipts] = useState([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [recording, setRecording] = useState(false)
  const [uploading, setUploading] = useState(false)
  const listRef = useRef(null)
  // Message ids are UUIDs; `seq` is each message's increasing position in the chat.
  const lastId = messages?.length ? messages[messages.length - 1].seq : 0
  const lastIdRef = useRef(0)
  useEffect(() => {
    lastIdRef.current = lastId
  }, [lastId])
  const withId = target.key

  // Load the latest messages, then poll for newer ones.
  useEffect(() => {
    let stopped = false
    let timer
    teamApi
      .chatMessages(withId)
      .then((res) => {
        if (stopped) return
        setMessages(res.messages)
        setReceipts(res.receipts)
      })
      .catch((err) => toast.error(err.message))
    // Polling also refreshes the receipts, so ticks turn from ✓ to ✓✓ to blue.
    const tick = async () => {
      try {
        const res = await teamApi.chatMessages(withId, { after: lastIdRef.current })
        const newer = res.messages
        if (!stopped) setReceipts(res.receipts)
        if (!stopped && newer.length)
          setMessages((current) => {
            const seen = new Set((current ?? []).map((m) => m.id))
            return [...(current ?? []), ...newer.filter((m) => !seen.has(m.id))]
          })
      } catch {
        // Retried on the next tick.
      }
      if (!stopped) timer = setTimeout(tick, POLL_MS)
    }
    timer = setTimeout(tick, POLL_MS)
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [withId, toast])

  // Keep the view pinned to the newest message.
  useEffect(() => {
    const el = listRef.current
    if (lastId && el) el.scrollTop = el.scrollHeight
  }, [lastId])

  // Mark what's on screen as read: now if the tab is visible, otherwise as soon as it is.
  useEffect(() => {
    if (!lastId) return
    const markRead = () => {
      if (document.visibilityState !== 'visible') return
      teamApi
        .markChatRead(withId, lastId)
        .then((r) => setUnread(r.unread))
        .catch(() => {})
    }
    markRead()
    document.addEventListener('visibilitychange', markRead)
    return () => document.removeEventListener('visibilitychange', markRead)
  }, [lastId, withId, setUnread])

  function addSent(sent) {
    setMessages((current) => ((current ?? []).some((m) => m.id === sent.id) ? current : [...(current ?? []), sent]))
    onSent()
  }

  // Sends the picked file right away, with anything typed in the box as its caption.
  function sendFile(file) {
    if (file.size > MAX_CHAT_FILE_BYTES) {
      toast.error('Files can be at most 20 MB.')
      return Upload.LIST_IGNORE
    }
    const caption = draft.trim()
    setUploading(true)
    teamApi
      .sendFile(withId, file, caption)
      .then((sent) => {
        addSent(sent)
        if (caption) setDraft('')
      })
      .catch((err) => toast.error(err.message))
      .finally(() => setUploading(false))
    return Upload.LIST_IGNORE
  }

  async function sendVoice(blob, duration, extension) {
    try {
      addSent(await teamApi.sendVoice(withId, blob, duration, extension))
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function send() {
    const body = draft.trim()
    if (!body) return
    setSending(true)
    try {
      const sent = await teamApi.sendChat(withId, body)
      setMessages((current) => (current ?? []).some((m) => m.id === sent.id) ? current : [...(current ?? []), sent])
      setDraft('')
      onSent()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSending(false)
    }
  }

  // The spelled-out receipt goes under your most recent message only.
  const lastMineId = [...(messages ?? [])].reverse().find((m) => m.sender === me.id)?.id
  const title = group ? group.name : peer ? displayName(peer) : 'Content team'
  const peerPresence = peer ? presence[String(peer.id)] ?? { online: peer.online, last_seen: peer.last_seen } : null
  const onlineCount = Object.values(presence).filter((p) => p.online).length + 1
  const subtitle = group
    ? `${group.member_count} members`
    : peer
      ? [peer.role, presenceLabel(peerPresence)].filter(Boolean).join(' · ')
      : `Everyone in Academic Content Writing · ${people.size} people · ${onlineCount} online`

  return (
    <Flex vertical style={{ height: '100%', minHeight: 0 }}>
      <Flex align="center" gap={12} className="chat-header">
        {onBack && <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack} aria-label="Back to conversations" />}
        {peer ? (
          <OnlineAvatar person={peer} online={peerPresence?.online} />
        ) : (
          <GroupAvatar team={!group} />
        )}
        <div style={{ minWidth: 0, flex: 1 }}>
          <Typography.Text strong style={{ display: 'block' }} ellipsis>
            {title}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 13, color: peerPresence?.online ? '#2b8a3e' : undefined }} ellipsis>
            {subtitle}
          </Typography.Text>
        </div>
        {group && (
          <Tooltip title={group.can_manage ? 'Rename, add or remove people' : 'Members and leave group'}>
            <Button icon={<SettingOutlined />} onClick={onManageGroup} aria-label="Group settings" />
          </Tooltip>
        )}
      </Flex>
      <div className="chat-messages" ref={listRef}>
        {!messages ? (
          <Skeleton active avatar paragraph={{ rows: 3 }} />
        ) : messages.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              peer
                ? `Say hello to ${peer.full_name || displayName(peer)}.`
                : group
                  ? `Start the conversation in ${group.name}.`
                  : 'Start the conversation with your team.'
            }
          />
        ) : (
          messages.map((m, i) => {
            const prev = messages[i - 1]
            const mine = m.sender === me.id
            const newDay = !prev || dayOf(prev.created_at) !== dayOf(m.created_at)
            const grouped =
              prev && !newDay && prev.sender === m.sender && new Date(m.created_at) - new Date(prev.created_at) < GROUP_GAP_MS
            const sender = people.get(m.sender)
            return (
              <div key={m.id}>
                {newDay && <div className="chat-day">{dayOf(m.created_at)}</div>}
                <Flex gap={10} justify={mine ? 'flex-end' : 'flex-start'} align="flex-end" style={{ marginTop: grouped ? 3 : 14 }}>
                  {!mine && (
                    <div style={{ width: 32, flexShrink: 0 }}>
                      {!grouped && sender && <PersonAvatar person={sender} size={32} />}
                    </div>
                  )}
                  <div style={{ maxWidth: '72%', minWidth: 0 }}>
                    {!mine && !grouped && !peer && (
                      <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>
                        {sender ? displayName(sender) : 'Former teammate'}
                      </Typography.Text>
                    )}
                    <div
                      className={`chat-bubble ${mine ? 'mine' : ''} ${m.audio ? 'voice' : ''}`}
                      title={new Date(m.created_at).toLocaleString()}
                    >
                      {m.audio && <audio controls preload="metadata" src={m.audio} aria-label="Voice message" />}
                      {m.file && <ChatAttachment file={m.file} mine={mine} />}
                      {m.body}
                      <span className="chat-time">
                        <span className="chat-time-text">{timeOf(m.created_at)}</span>
                        {mine && <Ticks message={m} receipts={receipts} />}
                      </span>
                    </div>
                    {m.id === lastMineId && <ReceiptLabel message={m} receipts={receipts} />}
                  </div>
                </Flex>
              </div>
            )
          })
        )}
      </div>
      <Flex gap={8} align="flex-end" className="chat-composer">
        {!recording && (
          <Upload accept={CHAT_FILE_ACCEPT} showUploadList={false} beforeUpload={sendFile} disabled={uploading}>
            <Tooltip title="Attach a file (Word, Excel, PowerPoint, PDF, CSV, images, ZIP · up to 20 MB)">
              <Button icon={<PaperClipOutlined />} loading={uploading} aria-label="Attach a file" />
            </Tooltip>
          </Upload>
        )}
        {!recording && (
          <Input.TextArea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder={`Message ${title} (Enter to send, Shift+Enter for a new line)`}
            autoSize={{ minRows: 1, maxRows: 5 }}
            maxLength={4000}
            autoFocus
          />
        )}
        {draft.trim() && !recording ? (
          <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={send} aria-label="Send" />
        ) : (
          <Flex flex={recording ? 1 : undefined} justify="flex-end">
            <VoiceRecorder onSend={sendVoice} onRecordingChange={setRecording} targetName={title} />
          </Flex>
        )}
      </Flex>
    </Flex>
  )
}

export default function Chat() {
  const { message } = App.useApp()
  const chat = useChat()
  const screens = Grid.useBreakpoint()
  const [data, setData] = useState(null)
  const [query, setQuery] = useState('')
  const [showList, setShowList] = useState(true)
  const [groupModal, setGroupModal] = useState(null) // null, 'new', or the group being edited
  const active = chat.active ?? 'team'
  const narrow = !screens.md

  const load = useCallback(() => {
    teamApi
      .chatContacts()
      .then(setData)
      .catch((err) => message.error(err.message))
  }, [message])

  // Reload the list (last messages) whenever the poller sees new messages.
  useEffect(load, [load, chat.version])

  // Also refresh it now and then, so new groups and last-seen times show up.
  useEffect(() => {
    const timer = setInterval(load, 20000)
    return () => clearInterval(timer)
  }, [load])

  // Tell the poller which conversation is on screen, so it doesn't notify about it.
  const { setActive } = chat
  useEffect(() => {
    setActive((current) => current ?? 'team')
    return () => setActive(null)
  }, [setActive])

  const people = useMemo(() => {
    const map = new Map()
    if (data) for (const p of [data.me, ...data.contacts]) map.set(p.id, p)
    return map
  }, [data])

  const contacts = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    return data.contacts
      .filter((c) => `${displayName(c)} ${c.role} ${c.email}`.toLowerCase().includes(q))
      .sort((a, b) => (b.last_message?.seq ?? 0) - (a.last_message?.seq ?? 0) || displayName(a).localeCompare(displayName(b)))
  }, [data, query])

  function open(conversation) {
    chat.setActive(conversation)
    setShowList(false)
  }

  const groups = data?.groups ?? []
  const shownGroups = groups.filter((g) => g.name.toLowerCase().includes(query.trim().toLowerCase()))
  const group = active.startsWith('g') ? groups.find((g) => g.key === active) : null
  const peer = active === 'team' || group ? null : data?.contacts.find((c) => String(c.id) === active)
  const target = { key: active, peer, group }
  const onlineOf = (c) => chat.presence[String(c.id)]?.online ?? c.online

  const list = (
    <Flex vertical style={{ height: '100%', minHeight: 0 }}>
      <div style={{ padding: 12 }}>
        <Input allowClear prefix={<SearchOutlined />} placeholder="Search your team" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="chat-contacts">
        {!data ? (
          <div style={{ padding: 16 }}>
            <Skeleton active avatar paragraph={{ rows: 1 }} />
          </div>
        ) : (
          <>
            <ContactRow
              selected={active === 'team'}
              avatar={<GroupAvatar team />}
              name="Content team"
              subtitle={preview(data.team.last_message, data.me.id)}
              unread={chat.unread.team ?? 0}
              onClick={() => open('team')}
            />
            <div className="chat-section-row">
              <Typography.Text type="secondary" className="cap-group-label">
                Groups · {groups.length}
              </Typography.Text>
              <Button size="small" type="text" icon={<PlusOutlined />} onClick={() => setGroupModal('new')}>
                New group
              </Button>
            </div>
            {shownGroups.map((g) => (
              <ContactRow
                key={g.key}
                selected={active === g.key}
                avatar={<GroupAvatar />}
                name={g.name}
                subtitle={g.last_message ? preview(g.last_message, data.me.id) : `${g.member_count} members`}
                unread={chat.unread[g.key] ?? 0}
                onClick={() => open(g.key)}
              />
            ))}
            <div className="chat-section-row">
              <Typography.Text type="secondary" className="cap-group-label">
                People · {data.contacts.length} ·{' '}
                <span style={{ color: '#2b8a3e' }}>{data.contacts.filter(onlineOf).length} online</span>
              </Typography.Text>
            </div>
            {contacts.map((c) => (
              <ContactRow
                key={c.id}
                selected={active === String(c.id)}
                avatar={<OnlineAvatar person={c} online={onlineOf(c)} />}
                name={displayName(c)}
                subtitle={c.last_message ? preview(c.last_message, data.me.id) : c.role}
                unread={chat.unread[String(c.id)] ?? 0}
                onClick={() => open(String(c.id))}
              />
            ))}
          </>
        )}
      </div>
    </Flex>
  )

  const conversation =
    data && (active === 'team' || peer || group) ? (
      <Conversation
        key={active}
        me={data.me}
        target={target}
        people={people}
        onBack={narrow ? () => setShowList(true) : null}
        onSent={load}
        onManageGroup={() => setGroupModal(group)}
      />
    ) : (
      <Flex align="center" justify="center" style={{ height: '100%' }}>
        {data ? <Empty description="Pick someone to chat with." /> : <Skeleton active />}
      </Flex>
    )

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="flex-end" wrap gap={12}>
        <div>
          <Typography.Title level={3} style={{ marginBottom: 4 }}>
            Team chat
          </Typography.Title>
          <Typography.Text type="secondary">
            For the Academic Content Writing team only. Message the whole team, a group, or anyone in it.
          </Typography.Text>
        </div>
        <NotificationSwitch />
      </Flex>
      <Card className="chat-card" styles={{ body: { padding: 0, height: '100%' } }}>
        {narrow ? (
          showList ? list : conversation
        ) : (
          <div className="chat-layout">
            <div className="chat-sidebar">{list}</div>
            <div className="chat-main">{conversation}</div>
          </div>
        )}
      </Card>
      {data && (
        <GroupModal
          open={Boolean(groupModal)}
          group={groupModal === 'new' ? null : groupModal}
          me={data.me}
          people={data.contacts}
          onClose={() => setGroupModal(null)}
          onSaved={(saved) => {
            setGroupModal(null)
            load()
            open(saved.key)
          }}
          onLeft={() => {
            setGroupModal(null)
            chat.setActive('team')
            load()
          }}
        />
      )}
    </Flex>
  )
}
