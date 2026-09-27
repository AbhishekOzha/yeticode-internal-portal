import { useEffect, useState } from 'react'
import { BellOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { Card, Flex, Typography } from 'antd'
import { teamApi } from '../api'
import { daysLabel, shiftLabel } from '../team'
import { NotificationSwitch } from './NotificationSwitch'

// The signed-in person's office hours, on their dashboard.
export function MyShift() {
  const [shift, setShift] = useState(undefined)

  useEffect(() => {
    teamApi
      .myOfficeHours()
      .then((data) => setShift(data.office_hours))
      .catch(() => setShift(null))
  }, [])

  if (!shift) return null
  return (
    <Card>
      <Flex justify="space-between" align="center" wrap gap={16}>
        <Flex align="center" gap={16}>
          <span className="section-icon" style={{ color: '#0b7285', background: '#0b72851f' }}>
            <ClockCircleOutlined />
          </span>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              Your office hours
            </Typography.Text>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {shiftLabel(shift)}
            </Typography.Title>
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              {daysLabel(shift.work_days)}
              {shift.reminders && (
                <>
                  {' · '}
                  <BellOutlined /> Reminders 30, 15 and 5 min before start, and 5 min before log-out
                </>
              )}
            </Typography.Text>
          </div>
        </Flex>
        {shift.reminders && <NotificationSwitch />}
      </Flex>
    </Card>
  )
}
