import { useState } from 'react'
import { BellOutlined, CheckCircleFilled } from '@ant-design/icons'
import { Button, Typography } from 'antd'
import { notificationPermission, requestNotifications } from '../notify'

// Lets someone allow desktop notifications (browsers only ask after a click).
export function NotificationSwitch({ size = 'middle' }) {
  const [permission, setPermission] = useState(notificationPermission)
  if (permission === 'unsupported') return null
  if (permission === 'granted') {
    return (
      <Typography.Text type="secondary" style={{ fontSize: 13 }}>
        <CheckCircleFilled style={{ color: '#2b8a3e' }} /> Desktop notifications on
      </Typography.Text>
    )
  }
  if (permission === 'denied') {
    return (
      <Typography.Text type="secondary" style={{ fontSize: 13 }}>
        Desktop notifications are blocked in this browser's site settings.
      </Typography.Text>
    )
  }
  return (
    <Button size={size} icon={<BellOutlined />} onClick={async () => setPermission(await requestNotifications())}>
      Turn on desktop notifications
    </Button>
  )
}
