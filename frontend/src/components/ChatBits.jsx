import { useEffect, useMemo, useState } from 'react'
import { TeamOutlined } from '@ant-design/icons'
import { App, Avatar, Badge, Button, Flex, Form, Input, Modal, Popconfirm, Select, Tooltip, Typography } from 'antd'
import { teamApi } from '../api'
import { displayName } from '../people'
import { receiptState } from '../team'
import { PersonAvatar } from './People'

// A person's photo with a green dot while they're online.
export function OnlineAvatar({ person, online, size = 40 }) {
  return (
    <Badge dot={online} color="#2b8a3e" offset={[-size * 0.12, size * 0.85]} title={online ? 'Online' : undefined}>
      <PersonAvatar person={person} size={size} />
    </Badge>
  )
}

export function GroupAvatar({ size = 40, team = false }) {
  return (
    <Avatar
      size={size}
      icon={<TeamOutlined />}
      style={{ background: team ? '#8b3fd9' : '#0b7285', flexShrink: 0 }}
    />
  )
}

const TICK_COLORS = {
  sent: 'rgba(255, 255, 255, 0.6)',
  delivered: '#ffffff',
  // Green reads clearly on the blue bubble (WhatsApp's blue wouldn't).
  seen: '#4ade80',
}
const RECEIPT_LABELS = { sent: 'Sent', delivered: 'Delivered', seen: 'Seen' }

function TickIcon({ double, color }) {
  return (
    <svg width={double ? 20 : 14} height="13" viewBox={double ? '0 0 20 13' : '0 0 14 13'} aria-hidden="true">
      <path d="M1.5 7l3.8 3.8L12.5 2.5" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      {double && (
        <path d="M9 10.3l.5.5L17.5 2.5" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      )}
    </svg>
  )
}

function describe(r) {
  if (r.total <= 1) return RECEIPT_LABELS[r.state]
  if (r.state === 'seen') return `Seen by everyone (${r.total})`
  const names = r.seen.map((x) => x.name)
  return `Seen by ${r.seen.length} of ${r.total}${names.length ? `: ${names.join(', ')}` : ''} · delivered to ${r.delivered.length}`
}

// ✓ sent, ✓✓ delivered, green ✓✓ seen. In groups the tooltip says who has seen it.
export function Ticks({ message, receipts }) {
  const r = receiptState(message, receipts)
  if (!r) return null
  const title = describe(r)
  return (
    <Tooltip title={title}>
      <span className={`chat-ticks ${r.state}`} aria-label={title}>
        <TickIcon double={r.state !== 'sent'} color={TICK_COLORS[r.state]} />
      </span>
    </Tooltip>
  )
}

// A small "Sent / Delivered / Seen" line under your latest message, spelled out.
export function ReceiptLabel({ message, receipts }) {
  const r = receiptState(message, receipts)
  if (!r) return null
  const text = r.total > 1 && r.state !== 'seen' && r.seen.length ? `Seen by ${r.seen.length} of ${r.total}` : r.total > 1 && r.state === 'seen' ? 'Seen by everyone' : RECEIPT_LABELS[r.state]
  return <div className={`chat-receipt-label ${r.state}`}>{text}</div>
}

// Create a group, or (with `group`) rename it, add or remove people, or leave it.
export function GroupModal({ open, group, me, people, onClose, onSaved, onLeft }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [busy, setBusy] = useState(false)
  const editing = Boolean(group)
  const canManage = !editing || group.can_manage

  useEffect(() => {
    if (!open) return
    form.setFieldsValue(
      editing ? { name: group.name, members: group.members.filter((id) => id !== me.id) } : { name: '', members: [] },
    )
  }, [open, editing, group, me, form])

  const options = useMemo(
    () =>
      people.map((p) => ({
        value: p.id,
        label: (
          <Flex align="center" gap={8}>
            <PersonAvatar person={p} size={22} />
            {displayName(p)}
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {p.role}
            </Typography.Text>
          </Flex>
        ),
        search: `${displayName(p)} ${p.role}`,
      })),
    [people],
  )

  async function handleFinish({ name, members }) {
    setBusy(true)
    try {
      let saved
      if (editing) {
        const before = new Set(group.members.filter((id) => id !== me.id))
        const after = new Set(members)
        saved = await teamApi.updateGroup(group.id, {
          name: name.trim(),
          add: [...after].filter((id) => !before.has(id)),
          remove: [...before].filter((id) => !after.has(id)),
        })
      } else {
        saved = await teamApi.createGroup(name.trim(), members)
      }
      message.success(editing ? 'Group updated.' : `${saved.name} created.`)
      onSaved(saved)
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function leave() {
    try {
      await teamApi.leaveGroup(group.id)
      message.success(`You left ${group.name}.`)
      onLeft()
    } catch (err) {
      message.error(err.message)
    }
  }

  return (
    <Modal
      open={open}
      title={editing ? group.name : 'New group'}
      onCancel={onClose}
      destroyOnHidden
      footer={
        <Flex justify="space-between">
          {editing ? (
            <Popconfirm title={`Leave ${group.name}?`} okText="Leave" okButtonProps={{ danger: true }} onConfirm={leave}>
              <Button danger type="text">
                Leave group
              </Button>
            </Popconfirm>
          ) : (
            <span />
          )}
          <Flex gap={8}>
            <Button onClick={onClose}>{canManage ? 'Cancel' : 'Close'}</Button>
            {canManage && (
              <Button type="primary" loading={busy} onClick={() => form.submit()}>
                {editing ? 'Save' : 'Create group'}
              </Button>
            )}
          </Flex>
        </Flex>
      }
    >
      <Form form={form} layout="vertical" onFinish={handleFinish} disabled={!canManage} style={{ marginTop: 16 }}>
        <Form.Item label="Group name" name="name" rules={[{ required: true, whitespace: true, message: 'Name the group' }]}>
          <Input maxLength={80} placeholder="e.g. Order 4512 writers" autoFocus />
        </Form.Item>
        <Form.Item
          label="Members"
          name="members"
          rules={[{ required: true, type: 'array', min: 1, message: 'Add at least one person' }]}
          extra={
            canManage
              ? 'Only people in Academic Content Writing. You are included automatically.'
              : 'Only the person who made this group, or the Production Manager, can change it.'
          }
          style={{ marginBottom: 0 }}
        >
          <Select mode="multiple" options={options} optionFilterProp="search" placeholder="Choose people" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
