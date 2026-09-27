import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { App, Avatar } from 'antd'
import { teamApi } from '../api'
import { desktopNotify } from '../notify'
import { colorFor, displayName, initials } from '../people'
import { ChatContext, conversationOf, inTeam } from '../team'

const POLL_MS = 4000

// Polls for new team chat messages while the app is open: keeps unread counts
// for the sidebar badge and shows a notification for each new message, unless
// that conversation is already open on screen.
export function ChatProvider({ user, children }) {
  const enabled = inTeam(user)
  const { notification } = App.useApp()
  const [unread, setUnread] = useState({})
  const [version, setVersion] = useState(0)
  const [active, setActive] = useState(null)
  const latestId = useRef(null)
  const activeRef = useRef(null)
  useEffect(() => {
    activeRef.current = active
  }, [active])

  const poll = useCallback(async () => {
    const updates = await teamApi.chatUpdates(latestId.current)
    setUnread(updates.unread)
    const first = latestId.current === null
    latestId.current = updates.latest_id
    if (first || !updates.new.length) return
    setVersion((v) => v + 1)
    for (const message of updates.new) {
      const conversation = conversationOf(message, user.id)
      const onScreen = activeRef.current === conversation && document.visibilityState === 'visible'
      if (onScreen) continue
      const sender = message.sender_person
      const title = conversation === 'team' ? `${displayName(sender)} in Content team` : displayName(sender)
      const open = () => {
        setActive(conversation)
        window.location.hash = 'chat'
      }
      notification.open({
        key: `chat-${conversation}`,
        title,
        description: message.body.length > 140 ? `${message.body.slice(0, 140)}…` : message.body,
        icon: (
          <Avatar src={sender.avatar || undefined} style={{ background: sender.avatar ? undefined : colorFor(displayName(sender)) }}>
            {initials(displayName(sender))}
          </Avatar>
        ),
        placement: 'bottomRight',
        onClick: () => {
          open()
          notification.destroy(`chat-${conversation}`)
        },
        style: { cursor: 'pointer' },
      })
      if (document.visibilityState !== 'visible') {
        desktopNotify(title, { body: message.body, icon: sender.avatar, tag: `chat-${conversation}`, onClick: open })
      }
    }
  }, [notification, user.id])

  useEffect(() => {
    if (!enabled) return
    let stopped = false
    let timer
    const tick = async () => {
      try {
        await poll()
      } catch {
        // A missed poll is retried on the next tick.
      }
      if (!stopped) timer = setTimeout(tick, POLL_MS)
    }
    tick()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [enabled, poll])

  const value = useMemo(
    () => ({
      enabled,
      unread,
      totalUnread: Object.values(unread).reduce((a, b) => a + b, 0),
      version,
      active,
      setActive,
      setUnread,
      refresh: () => poll().catch(() => {}),
    }),
    [enabled, unread, version, active, poll],
  )
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}
