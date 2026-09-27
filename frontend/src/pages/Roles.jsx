import { useEffect, useMemo, useState } from 'react'
import { LockOutlined, TeamOutlined } from '@ant-design/icons'
import { App, Button, Card, Checkbox, Col, Flex, Row, Skeleton, Tabs, Tag, Tooltip, Typography } from 'antd'
import { api } from '../api'
import { unitColor } from '../colors'

// Show a unit's own capability group first, then the shared ones.
const GROUP_ORDER = ['General', 'Web App Development', 'Training', 'Academic Content Writing', 'HR']

function RoleCard({ role, capabilities, onSaved }) {
  const { message } = App.useApp()
  const [selected, setSelected] = useState(() => new Set(role.capabilities))
  const [busy, setBusy] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const companyWide = role.unit_id === null
  const dirty = selected.size !== role.capabilities.length || role.capabilities.some((c) => !selected.has(c))

  const groups = useMemo(() => {
    const byGroup = new Map()
    for (const cap of capabilities) {
      if (!byGroup.has(cap.group)) byGroup.set(cap.group, [])
      byGroup.get(cap.group).push(cap)
    }
    const relevant = (group) =>
      showAll || group === 'General' || group === 'HR' || group === role.unit || byGroup.get(group).some((c) => selected.has(c.code))
    return GROUP_ORDER.filter((g) => byGroup.has(g) && relevant(g)).map((g) => [g, byGroup.get(g)])
  }, [capabilities, showAll, role.unit, selected])

  function toggle(code, checked) {
    setSelected((current) => {
      const next = new Set(current)
      if (checked) next.add(code)
      else next.delete(code)
      return next
    })
  }

  async function save() {
    setBusy(true)
    try {
      const ordered = capabilities.map((c) => c.code).filter((code) => selected.has(code))
      const updated = await api.updateRole(role.id, { capabilities: ordered })
      onSaved(updated)
      message.success(`${role.name} updated.`)
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      className="role-card"
      title={
        <Flex vertical gap={2} style={{ padding: '6px 0' }}>
          <span>{role.name}</span>
          <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
            <TeamOutlined /> {role.member_count} active {role.member_count === 1 ? 'person' : 'people'} · {selected.size} permissions
          </Typography.Text>
        </Flex>
      }
      extra={
        <Button type="primary" size="small" disabled={!dirty} loading={busy} onClick={save}>
          Save
        </Button>
      }
    >
      <Flex vertical gap={14}>
        {groups.map(([group, caps]) => (
          <div key={group}>
            <Typography.Text type="secondary" className="cap-group-label">
              {group}
            </Typography.Text>
            <Flex vertical gap={6} style={{ marginTop: 6 }}>
              {caps.map((cap) => {
                const locked = cap.cross_unit && !companyWide
                const box = (
                  <Checkbox
                    checked={selected.has(cap.code)}
                    disabled={locked}
                    onChange={(e) => toggle(cap.code, e.target.checked)}
                  >
                    {cap.label} {locked && <LockOutlined style={{ fontSize: 11, opacity: 0.6 }} />}
                  </Checkbox>
                )
                return (
                  <Tooltip
                    key={cap.code}
                    title={locked ? 'Only company-wide roles can see across units.' : cap.description}
                    placement="left"
                    mouseEnterDelay={0.4}
                  >
                    <span style={{ alignSelf: 'flex-start' }}>{box}</span>
                  </Tooltip>
                )
              })}
            </Flex>
          </div>
        ))}
        <Button type="link" size="small" style={{ alignSelf: 'flex-start', padding: 0 }} onClick={() => setShowAll((s) => !s)}>
          {showAll ? 'Show relevant permissions only' : 'Show permissions from other units'}
        </Button>
      </Flex>
    </Card>
  )
}

export default function Roles() {
  const { message } = App.useApp()
  const [roles, setRoles] = useState(null)
  const [capabilities, setCapabilities] = useState([])

  useEffect(() => {
    Promise.all([api.listRoles(), api.listCapabilities()])
      .then(([r, c]) => {
        setRoles(r)
        setCapabilities(c)
      })
      .catch((err) => message.error(err.message))
  }, [message])

  const units = useMemo(() => {
    const seen = new Map()
    for (const r of roles ?? []) seen.set(r.unit_code ?? 'all', r.unit)
    const order = ['web', 'training', 'content', 'all']
    return order.filter((k) => seen.has(k)).map((k) => [k, seen.get(k)])
  }, [roles])

  function handleSaved(updated) {
    setRoles((current) => current.map((r) => (r.id === updated.id ? updated : r)))
  }

  return (
    <Flex vertical gap={20}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          What each role can do
        </Typography.Title>
        <Typography.Text type="secondary">
          Changes apply to everyone with that role the next time they open the app. Units stay isolated: only
          company-wide roles can see across units.
        </Typography.Text>
      </div>
      {!roles ? (
        <Card>
          <Skeleton active />
        </Card>
      ) : (
        <Tabs
          size="large"
          items={units.map(([code, name]) => {
            const unitRoles = roles.filter((r) => (r.unit_code ?? 'all') === code)
            return {
              key: code,
              label: (
                <Flex align="center" gap={8}>
                  <span className="unit-dot" style={{ background: unitColor(code).color }} />
                  {name === 'All units' ? 'Company-wide' : name}
                  <Tag variant="filled" style={{ marginInlineEnd: 0 }}>{unitRoles.length}</Tag>
                </Flex>
              ),
              children: (
                <Row gutter={[16, 16]}>
                  {unitRoles.map((role) => (
                    <Col key={role.id} xs={24} md={12} xxl={8}>
                      <RoleCard role={role} capabilities={capabilities} onSaved={handleSaved} />
                    </Col>
                  ))}
                </Row>
              ),
            }
          })}
        />
      )}
    </Flex>
  )
}
