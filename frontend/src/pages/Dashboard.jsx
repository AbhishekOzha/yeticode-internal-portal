import { useEffect, useMemo, useState } from 'react'
import { ArrowRightOutlined, CheckCircleFilled, ClockCircleOutlined } from '@ant-design/icons'
import { Button, Card, Col, Flex, Progress, Row, Skeleton, Statistic, Tag, Typography } from 'antd'
import { api } from '../api'
import { capabilityMeta } from '../capabilities'
import { displayName } from '../people'
import { UNIT_COLORS, unitColor } from '../colors'

// Sections that open a real page today; the rest are on the roadmap.
const LIVE = {
  view_unit_directory: 'directory',
  view_all_employee_records: 'directory',
  manage_unit_users: 'users',
  manage_users: 'users',
  manage_roles: 'roles',
  manage_payroll: 'payroll',
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

function Hero({ user }) {
  const unit = user.is_super_admin ? 'all' : user.unit?.code ?? 'all'
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
  return (
    <div className="hero">
      <div className="hero-glow" />
      <Typography.Text className="hero-date">{today}</Typography.Text>
      <h1 className="hero-title">
        {greeting()}, {user.first_name || displayName(user)}
      </h1>
      <Flex gap={8} wrap>
        <Tag className="hero-tag">{user.is_super_admin ? 'Super Admin' : user.role.name}</Tag>
        <Tag className="hero-tag" style={{ borderColor: unitColor(unit).color }}>
          {user.unit ? user.unit.name : 'All units'}
        </Tag>
      </Flex>
    </div>
  )
}

function TeamStats({ user }) {
  const [users, setUsers] = useState(null)
  useEffect(() => {
    api.listUsers().then(setUsers).catch(() => setUsers([]))
  }, [])

  const stats = useMemo(() => {
    if (!users) return null
    const active = users.filter((u) => u.is_active)
    const byUnit = {}
    for (const u of active) {
      const key = u.unit_code ?? 'all'
      byUnit[key] = byUnit[key] ?? { name: u.unit, count: 0 }
      byUnit[key].count += 1
    }
    const neverSignedIn = active.filter((u) => !u.last_login).length
    return { total: users.length, active: active.length, inactive: users.length - active.length, byUnit, neverSignedIn }
  }, [users])

  if (!stats) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 2 }} />
      </Card>
    )
  }

  const order = ['web', 'training', 'content', 'all']
  const scope = user.is_super_admin ? 'Across all units' : `In ${user.unit.name}`
  const tiles = [
    { title: 'Active accounts', value: stats.active, note: scope },
    { title: 'Deactivated', value: stats.inactive, note: 'Cannot sign in' },
    { title: 'Never signed in', value: stats.neverSignedIn, note: 'Active accounts not used yet' },
  ]
  const unitRows = order.filter((k) => stats.byUnit[k])
  return (
    <Row gutter={[16, 16]}>
      {tiles.map((t) => (
        <Col key={t.title} xs={24} sm={8}>
          <Card className="stat-card">
            <Statistic title={t.title} value={t.value} />
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>{t.note}</Typography.Text>
          </Card>
        </Col>
      ))}
      {unitRows.length > 1 && (
        <Col span={24}>
          <Card title="People by unit" size="small" styles={{ body: { padding: '16px 20px' } }}>
            <Row gutter={[32, 12]}>
              {unitRows.map((k) => (
                <Col key={k} xs={24} sm={12} xl={6}>
                  <Flex justify="space-between" style={{ fontSize: 13 }}>
                    <span>{k === 'all' ? 'Company-wide' : stats.byUnit[k].name}</span>
                    <strong>{stats.byUnit[k].count}</strong>
                  </Flex>
                  <Progress
                    percent={Math.round((stats.byUnit[k].count / Math.max(stats.active, 1)) * 100)}
                    showInfo={false}
                    size="small"
                    strokeColor={(UNIT_COLORS[k] ?? UNIT_COLORS.all).color}
                  />
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      )}
    </Row>
  )
}

function SectionCard({ section }) {
  const meta = capabilityMeta(section.key)
  const Icon = meta.icon
  const target = LIVE[section.key]
  return (
    <Card
      hoverable={Boolean(target)}
      className={`section-card ${target ? 'live' : ''}`}
      onClick={target ? () => (window.location.hash = target) : undefined}
    >
      <Flex justify="space-between" align="flex-start">
        <span className="section-icon" style={{ color: meta.color, background: `${meta.color}1f` }}>
          <Icon />
        </span>
        {target ? (
          <Tag color="success" variant="filled" icon={<CheckCircleFilled />}>Available</Tag>
        ) : (
          <Tag variant="filled" icon={<ClockCircleOutlined />}>Coming soon</Tag>
        )}
      </Flex>
      <Typography.Title level={5} style={{ margin: '16px 0 6px' }}>
        {section.title}
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginBottom: target ? 12 : 0, minHeight: 44 }}>
        {section.description}
      </Typography.Paragraph>
      {target && (
        <Button type="link" style={{ padding: 0 }}>
          Open <ArrowRightOutlined />
        </Button>
      )}
    </Card>
  )
}

export default function Dashboard({ user }) {
  const sections = [...user.dashboard].sort((a, b) => Number(Boolean(LIVE[b.key])) - Number(Boolean(LIVE[a.key])))
  return (
    <Flex vertical gap={24}>
      <Hero user={user} />
      {user.can_manage_users && (
        <section>
          <Typography.Title level={5} className="section-heading">Team at a glance</Typography.Title>
          <TeamStats user={user} />
        </section>
      )}
      <section>
        <Typography.Title level={5} className="section-heading">Your workspace</Typography.Title>
        {sections.length === 0 ? (
          <Card>
            <Typography.Text type="secondary">Your role has no sections yet. Ask your administrator.</Typography.Text>
          </Card>
        ) : (
          <Row gutter={[16, 16]}>
            {sections.map((section) => (
              <Col key={section.key} xs={24} sm={12} xl={8} xxl={6}>
                <SectionCard section={section} />
              </Col>
            ))}
          </Row>
        )}
      </section>
      {user.is_super_admin && (
        <Typography.Text type="secondary" style={{ fontSize: 13 }}>
          Need something the app doesn't cover yet? The <a href="/admin/">Django admin panel</a> is still available to Super Admins.
        </Typography.Text>
      )}
    </Flex>
  )
}
