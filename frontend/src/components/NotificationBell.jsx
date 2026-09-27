import { useCallback, useEffect, useRef, useState } from 'react'
import { BellOutlined, CalendarOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { App, Badge, Button, Dropdown, Empty, Flex, Tooltip, Typography } from 'antd'
import { notificationsApi } from '../api'
import { desktopNotify } from '../notify'

const POLL_MS = 15000

const ICONS = {
  leave_requested: <CalendarOutlined style={{ color: '#3451d1' }} />,
  leave_cancelled: <CalendarOutlined style={{ color: '#64748b' }} />,
  leave_approved: <CheckOutlined style={{ color: '#2b8a3e' }} />,
  leave_rejected: <CloseOutlined style={{ color: '#e03131' }} />,
  leave_decided: <CheckOutlined style={{ color: '#64748b' }} />,
}

function ago(iso) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

// The bell in the header: unread count, the latest notifications, and a pop-up
// (plus a desktop notification when allowed) whenever a new one arrives.
export function NotificationBell() {
  const { notification } = App.useApp()
  const [data, setData] = useState({ unread: 0, notifications: [] })
  const known = useRef(null) // ids already seen, so only new ones pop up

  const open = useCallback((n) => {
    if (!n.read) notificationsApi.markRead([n.id]).then((r) => setData((d) => ({ ...d, unread: r.unread })))
    setData((d) => ({ ...d, notifications: d.notifications.map((x) => (x.id === n.id ? { ...x, read: true } : x)) }))
    if (n.link) window.location.hash = n.link
  }, [])

  const load = useCallback(async () => {
    const next = await notificationsApi.list()
    const first = known.current === null
    const fresh = first ? [] : next.notifications.filter((n) => !n.read && !known.current.has(n.id))
    known.current = new Set(next.notifications.map((n) => n.id))
    setData(next)
    for (const n of fresh.reverse()) {
      notification.open({
        key: `note-${n.id}`,
        title: n.title,
        description: n.body,
        icon: ICONS[n.kind] ?? <BellOutlined />,
        placement: 'topRight',
        duration: 8,
        style: { cursor: n.link ? 'pointer' : undefined },
        onClick: () => {
          open(n)
          notification.destroy(`note-${n.id}`)
        },
      })
      if (document.visibilityState !== 'visible') desktopNotify(n.title, { body: n.body, tag: n.id, onClick: () => open(n) })
    }
  }, [notification, open])

  useEffect(() => {
    let stopped = false
    let timer
    const tick = async () => {
      try {
        await load()
      } catch {
        // Retried on the next tick.
      }
      if (!stopped) timer = setTimeout(tick, POLL_MS)
    }
    tick()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [load])

  async function markAll() {
    const r = await notificationsApi.markRead()
    setData((d) => ({ unread: r.unread, notifications: d.notifications.map((n) => ({ ...n, read: true })) }))
  }

  const panel = (
    <div className="bell-panel">
      <Flex justify="space-between" align="center" className="bell-panel-head">
        <Typography.Text strong>Notifications</Typography.Text>
        {data.unread > 0 && (
          <Button type="link" size="small" onClick={markAll}>
            Mark all read
          </Button>
        )}
      </Flex>
      {data.notifications.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Nothing yet" style={{ padding: '16px 0' }} />
      ) : (
        <div className="bell-list">
          {data.notifications.map((n) => (
            <button key={n.id} type="button" className={`bell-item ${n.read ? '' : 'unread'}`} onClick={() => open(n)}>
              <span className="bell-icon">{ICONS[n.kind] ?? <BellOutlined />}</span>
              <span style={{ minWidth: 0, flex: 1 }}>
                <Typography.Text strong={!n.read} style={{ display: 'block' }}>
                  {n.title}
                </Typography.Text>
                {n.body && (
                  <Typography.Text type="secondary" style={{ fontSize: 13, display: 'block' }}>
                    {n.body}
                  </Typography.Text>
                )}
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {ago(n.created_at)}
                </Typography.Text>
              </span>
              {!n.read && <span className="bell-dot" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )

  return (
    <Dropdown trigger={['click']} popupRender={() => panel} placement="bottomRight">
      <Tooltip title="Notifications">
        <Badge count={data.unread} size="small" offset={[-4, 4]}>
          <Button type="text" shape="circle" aria-label={`Notifications (${data.unread} unread)`} icon={<BellOutlined />} />
        </Badge>
      </Tooltip>
    </Dropdown>
  )
}
