import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeftOutlined, SearchOutlined, SendOutlined, TeamOutlined } from '@ant-design/icons'
import { App, Avatar, Badge, Button, Card, Empty, Flex, Grid, Input, Skeleton, Typography } from 'antd'
import { teamApi } from '../api'
import { NotificationSwitch } from '../components/NotificationSwitch'
import { PersonAvatar } from '../components/People'
import { displayName } from '../people'
import { useChat } from '../team'

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
  return `${message.sender === meId ? 'You: ' : ''}${message.body}`
}

function TeamAvatar({ size = 40 }) {
  return <Avatar size={size} icon={<TeamOutlined />} style={{ background: '#8b3fd9', flexShrink: 0 }} />
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

function Conversation({ me, peer, people, onBack, onSent }) {
  const { message: toast } = App.useApp()
  const { setUnread } = useChat()
  const [messages, setMessages] = useState(null)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const listRef = useRef(null)
  const lastId = messages?.length ? messages[messages.length - 1].id : 0
  const lastIdRef = useRef(0)
  useEffect(() => {
    lastIdRef.current = lastId
  }, [lastId])
  const withId = peer ? String(peer.id) : 'team'

  // Load the latest messages, then poll for newer ones.
  useEffect(() => {
    let stopped = false
    let timer
    teamApi
      .chatMessages(withId)
      .then((list) => !stopped && setMessages(list))
      .catch((err) => toast.error(err.message))
    const tick = async () => {
      try {
        const newer = await teamApi.chatMessages(withId, { after: lastIdRef.current })
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

  const title = peer ? displayName(peer) : 'Content team'
  const subtitle = peer ? peer.role : `Everyone in Academic Content Writing · ${people.size} people`

  return (
    <Flex vertical style={{ height: '100%', minHeight: 0 }}>
      <Flex align="center" gap={12} className="chat-header">
        {onBack && <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack} aria-label="Back to conversations" />}
        {peer ? <PersonAvatar person={peer} size={40} /> : <TeamAvatar />}
        <div style={{ minWidth: 0 }}>
          <Typography.Text strong style={{ display: 'block' }} ellipsis>
            {title}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 13 }} ellipsis>
            {subtitle}
          </Typography.Text>
        </div>
      </Flex>
      <div className="chat-messages" ref={listRef}>
        {!messages ? (
          <Skeleton active avatar paragraph={{ rows: 3 }} />
        ) : messages.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={peer ? `Say hello to ${peer.full_name || displayName(peer)}.` : 'Start the conversation with your team.'}
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
                  <div style={{ maxWidth: '72%' }}>
                    {!mine && !grouped && !peer && (
                      <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>
                        {sender ? displayName(sender) : 'Former teammate'}
                      </Typography.Text>
                    )}
                    <div className={`chat-bubble ${mine ? 'mine' : ''}`} title={new Date(m.created_at).toLocaleString()}>
                      {m.body}
                      <span className="chat-time">{timeOf(m.created_at)}</span>
                    </div>
                  </div>
                </Flex>
              </div>
            )
          })
        )}
      </div>
      <Flex gap={8} align="flex-end" className="chat-composer">
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
          placeholder={`Message ${peer ? displayName(peer) : 'the team'} (Enter to send, Shift+Enter for a new line)`}
          autoSize={{ minRows: 1, maxRows: 5 }}
          maxLength={4000}
          autoFocus
        />
        <Button type="primary" icon={<SendOutlined />} loading={sending} disabled={!draft.trim()} onClick={send} aria-label="Send" />
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
      .sort((a, b) => (b.last_message?.id ?? 0) - (a.last_message?.id ?? 0) || displayName(a).localeCompare(displayName(b)))
  }, [data, query])

  function open(conversation) {
    chat.setActive(conversation)
    setShowList(false)
  }

  const peer = active === 'team' ? null : data?.contacts.find((c) => String(c.id) === active)

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
              avatar={<TeamAvatar />}
              name="Content team"
              subtitle={preview(data.team.last_message, data.me.id)}
              unread={chat.unread.team ?? 0}
              onClick={() => open('team')}
            />
            <Typography.Text type="secondary" className="cap-group-label" style={{ display: 'block', padding: '12px 16px 4px' }}>
              People · {data.contacts.length}
            </Typography.Text>
            {contacts.map((c) => (
              <ContactRow
                key={c.id}
                selected={active === String(c.id)}
                avatar={<PersonAvatar person={c} size={40} />}
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
    data && (active === 'team' || peer) ? (
      <Conversation
        key={active}
        me={data.me}
        peer={peer}
        people={people}
        onBack={narrow ? () => setShowList(true) : null}
        onSent={load}
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
            For the Academic Content Writing team only. Message the whole team or anyone in it.
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
    </Flex>
  )
}
