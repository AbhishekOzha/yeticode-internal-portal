import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CrownOutlined,
  EditOutlined,
  KeyOutlined,
  MoreOutlined,
  PlusOutlined,
  SearchOutlined,
  StopOutlined,
  UndoOutlined,
} from '@ant-design/icons'
import {
  App,
  Badge,
  Button,
  Card,
  Col,
  Drawer,
  Dropdown,
  Flex,
  Form,
  Input,
  Modal,
  Row,
  Segmented,
  Select,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { api } from '../api'
import { PersonCell, UnitTag } from '../components/People'
import { displayName } from '../people'

const SUPER_ADMIN = 'super_admin'

function relativeTime(iso) {
  if (!iso) return null
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000
  const units = [
    ['year', 31536000],
    ['month', 2592000],
    ['week', 604800],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ]
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit)
  }
  return 'just now'
}

// Puts DRF field errors ({"field": ["msg"]}) onto the matching form fields.
function applyServerErrors(form, err, fieldMap = {}) {
  const data = err.data && typeof err.data === 'object' ? err.data : null
  if (!data || data.detail) return false
  const fields = Object.entries(data)
    .filter(([name]) => name !== 'non_field_errors')
    .map(([name, errors]) => ({ name: fieldMap[name] ?? name, errors: [].concat(errors) }))
  if (!fields.length) return false
  form.setFields(fields)
  return true
}

function UserDrawer({ open, user, roles, currentUser, onClose, onSaved }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [busy, setBusy] = useState(false)
  const isNew = !user
  const isSelf = user?.id === currentUser.id

  useEffect(() => {
    if (!open) return
    form.resetFields()
    if (user) {
      form.setFieldsValue({
        email: user.email,
        username: user.username,
        first_name: user.first_name,
        last_name: user.last_name,
        role: user.is_super_admin ? SUPER_ADMIN : user.role,
        is_active: user.is_active,
      })
    } else {
      form.setFieldsValue({ is_active: true })
    }
  }, [open, user, form])

  const roleOptions = useMemo(() => {
    const groups = new Map()
    for (const role of roles) {
      if (!groups.has(role.unit)) groups.set(role.unit, [])
      groups.get(role.unit).push({ label: role.name, value: role.id })
    }
    const options = [...groups.entries()].map(([unit, opts]) => ({ label: unit, options: opts }))
    if (currentUser.is_super_admin) {
      options.unshift({
        label: 'Company',
        options: [{ label: 'Super Admin (all units)', value: SUPER_ADMIN }],
      })
    }
    return options
  }, [roles, currentUser])

  async function handleFinish(values) {
    setBusy(true)
    const payload = {
      email: values.email.trim(),
      username: (values.username || values.email).trim(),
      first_name: values.first_name.trim(),
      last_name: (values.last_name || '').trim(),
      is_active: values.is_active,
      is_super_admin: values.role === SUPER_ADMIN,
      role: values.role === SUPER_ADMIN ? null : values.role,
    }
    if (isNew) payload.password = values.password
    try {
      const saved = isNew ? await api.createUser(payload) : await api.updateUser(user.id, payload)
      message.success(isNew ? `${displayName(saved)} can now sign in.` : 'Changes saved.')
      onSaved()
    } catch (err) {
      if (!applyServerErrors(form, err, { is_super_admin: 'role' })) message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      size={520}
      destroyOnHidden
      title={isNew ? 'Add a user' : `Edit ${user ? displayName(user) : ''}`}
      extra={
        <Button type="primary" loading={busy} onClick={() => form.submit()}>
          {isNew ? 'Create account' : 'Save changes'}
        </Button>
      }
    >
      <Form form={form} layout="vertical" requiredMark="optional" onFinish={handleFinish}>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="First name" name="first_name" rules={[{ required: true, whitespace: true, message: 'Enter a first name' }]}>
              <Input autoFocus />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="Last name" name="last_name">
              <Input />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item
          label="Work email"
          name="email"
          extra="They sign in with this email."
          rules={[{ required: true, type: 'email', message: 'Enter a valid email address' }]}
        >
          <Input placeholder="name@yeticode.com" autoComplete="off" />
        </Form.Item>
        {!isNew && user?.username !== user?.email && (
          <Form.Item label="Username" name="username" extra="Older accounts may also sign in with a username.">
            <Input />
          </Form.Item>
        )}
        <Form.Item
          label="Role"
          name="role"
          rules={[{ required: true, message: 'Choose a role' }]}
          extra={isSelf ? 'You cannot change your own role.' : 'The role decides the unit and what they can see.'}
        >
          <Select
            placeholder="Choose a role"
            options={roleOptions}
            disabled={isSelf}
            showSearch={{ optionFilterProp: 'label' }}
          />
        </Form.Item>
        {isNew && (
          <Form.Item
            label="Temporary password"
            name="password"
            extra="At least 8 characters, not too common. Share it with them securely."
            rules={[{ required: true, message: 'Set a password' }, { min: 8, message: 'At least 8 characters' }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        )}
        {!isNew && !isSelf && (
          <Form.Item label="Account active" name="is_active" valuePropName="checked" extra="Deactivated users cannot sign in.">
            <Switch />
          </Form.Item>
        )}
      </Form>
    </Drawer>
  )
}

function ResetPasswordModal({ user, onClose }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [busy, setBusy] = useState(false)

  async function handleFinish({ password }) {
    setBusy(true)
    try {
      await api.updateUser(user.id, { password })
      message.success(`Password reset for ${displayName(user)}.`)
      onClose()
    } catch (err) {
      if (!applyServerErrors(form, err)) message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(user)}
      title={user ? `Reset password for ${displayName(user)}` : ''}
      okText="Reset password"
      confirmLoading={busy}
      onOk={() => form.submit()}
      onCancel={onClose}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={handleFinish} style={{ marginTop: 16 }}>
        <Form.Item
          label="New password"
          name="password"
          rules={[{ required: true, message: 'Enter a new password' }, { min: 8, message: 'At least 8 characters' }]}
        >
          <Input.Password autoFocus autoComplete="new-password" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default function Users({ user: currentUser }) {
  const { message, modal } = App.useApp()
  const [users, setUsers] = useState(null)
  const [roles, setRoles] = useState([])
  const [drawer, setDrawer] = useState({ open: false, user: null })
  const [resetting, setResetting] = useState(null)
  const [query, setQuery] = useState('')
  const [unit, setUnit] = useState('all')
  const [status, setStatus] = useState('active')

  const load = useCallback(() => {
    Promise.all([api.listUsers(), api.listRoles()])
      .then(([u, r]) => {
        setUsers(u)
        setRoles(r)
      })
      .catch((err) => message.error(err.message))
  }, [message])

  useEffect(load, [load])

  const units = useMemo(() => {
    const seen = new Map()
    for (const u of users ?? []) seen.set(u.unit_code ?? 'company', u.unit_code ? u.unit : 'Company-wide (Super Admin, Head HR)')
    return [...seen.entries()]
  }, [users])

  const counts = useMemo(() => {
    const all = users ?? []
    return { active: all.filter((u) => u.is_active).length, inactive: all.filter((u) => !u.is_active).length }
  }, [users])

  const rows = (users ?? []).filter((u) => {
    if (status === 'active' && !u.is_active) return false
    if (status === 'inactive' && u.is_active) return false
    if (unit !== 'all' && (u.unit_code ?? 'company') !== unit) return false
    const text = `${u.first_name} ${u.last_name} ${u.username} ${u.email} ${u.role_name ?? ''}`.toLowerCase()
    return text.includes(query.trim().toLowerCase())
  })

  function confirmToggle(target) {
    const deactivate = target.is_active
    modal.confirm({
      title: deactivate ? `Deactivate ${displayName(target)}?` : `Reactivate ${displayName(target)}?`,
      content: deactivate
        ? 'They will be signed out and cannot sign in until an administrator reactivates the account.'
        : 'They will be able to sign in again with their existing password.',
      okText: deactivate ? 'Deactivate' : 'Reactivate',
      okButtonProps: { danger: deactivate },
      onOk: async () => {
        try {
          await api.updateUser(target.id, { is_active: !deactivate })
          message.success(deactivate ? 'Account deactivated.' : 'Account reactivated.')
          load()
        } catch (err) {
          message.error(err.message)
        }
      },
    })
  }

  const columns = [
    {
      title: 'Name',
      key: 'name',
      render: (_, u) => <PersonCell person={u} muted={!u.is_active} />,
      sorter: (a, b) => displayName(a).localeCompare(displayName(b)),
    },
    {
      title: 'Role',
      key: 'role',
      render: (_, u) =>
        u.is_super_admin ? (
          <Tag icon={<CrownOutlined />} color="gold" variant="filled">Super Admin</Tag>
        ) : (
          u.role_name
        ),
      sorter: (a, b) => (a.role_name ?? '').localeCompare(b.role_name ?? ''),
    },
    {
      title: 'Unit',
      key: 'unit',
      render: (_, u) => <UnitTag code={u.unit_code} name={u.unit} />,
      responsive: ['md'],
    },
    {
      title: 'Status',
      key: 'status',
      render: (_, u) =>
        u.is_active ? <Badge status="success" text="Active" /> : <Badge status="default" text="Deactivated" />,
    },
    {
      title: 'Last sign-in',
      key: 'last_login',
      responsive: ['lg'],
      render: (_, u) =>
        u.last_login ? (
          <Tooltip title={new Date(u.last_login).toLocaleString()}>{relativeTime(u.last_login)}</Tooltip>
        ) : (
          <Typography.Text type="secondary">Never</Typography.Text>
        ),
    },
    {
      title: '',
      key: 'actions',
      align: 'right',
      width: 64,
      render: (_, u) => {
        const self = u.id === currentUser.id
        const items = [
          { key: 'edit', icon: <EditOutlined />, label: 'Edit details' },
          { key: 'password', icon: <KeyOutlined />, label: 'Reset password' },
        ]
        if (!self) {
          items.push({ type: 'divider' })
          items.push(
            u.is_active
              ? { key: 'toggle', icon: <StopOutlined />, label: 'Deactivate', danger: true }
              : { key: 'toggle', icon: <UndoOutlined />, label: 'Reactivate' },
          )
        }
        return (
          <Dropdown
            trigger={['click']}
            menu={{
              items,
              onClick: ({ key }) => {
                if (key === 'edit') setDrawer({ open: true, user: u })
                if (key === 'password') setResetting(u)
                if (key === 'toggle') confirmToggle(u)
              },
            }}
          >
            <Button type="text" icon={<MoreOutlined />} aria-label={`Actions for ${displayName(u)}`} />
          </Dropdown>
        )
      },
    },
  ]

  return (
    <Flex vertical gap={20}>
      <Flex justify="space-between" align="flex-end" wrap gap={16}>
        <div>
          <Typography.Title level={3} style={{ marginBottom: 4 }}>
            {currentUser.is_super_admin ? 'Everyone with an account' : `People in ${currentUser.unit.name}`}
          </Typography.Title>
          <Typography.Text type="secondary">
            Add people, assign roles and control who can sign in.
            {!currentUser.is_super_admin && ' You can only manage accounts in your own unit.'}
          </Typography.Text>
        </div>
        <Button type="primary" size="large" icon={<PlusOutlined />} onClick={() => setDrawer({ open: true, user: null })}>
          Add user
        </Button>
      </Flex>

      <Card styles={{ body: { padding: 0 } }}>
        <Flex gap={12} wrap align="center" justify="space-between" style={{ padding: 16 }}>
          <Flex gap={12} wrap align="center">
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="Search name, email or role"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ width: 280 }}
            />
            {units.length > 1 && (
              <Select
                value={unit}
                onChange={setUnit}
                style={{ minWidth: 210 }}
                options={[{ label: 'All units', value: 'all' }, ...units.map(([code, name]) => ({ label: name, value: code }))]}
              />
            )}
          </Flex>
          <Segmented
            value={status}
            onChange={setStatus}
            options={[
              { label: `Active (${counts.active})`, value: 'active' },
              { label: `Deactivated (${counts.inactive})`, value: 'inactive' },
              { label: 'All', value: 'all' },
            ]}
          />
        </Flex>
        <Table
          rowKey="id"
          loading={!users}
          columns={columns}
          dataSource={rows}
          rowClassName={(u) => (u.is_active ? '' : 'row-inactive')}
          pagination={{ pageSize: 15, hideOnSinglePage: true, showSizeChanger: false }}
          locale={{ emptyText: 'No users match these filters.' }}
          scroll={{ x: 640 }}
        />
      </Card>

      <UserDrawer
        open={drawer.open}
        user={drawer.user}
        roles={roles}
        currentUser={currentUser}
        onClose={() => setDrawer({ open: false, user: null })}
        onSaved={() => {
          setDrawer({ open: false, user: null })
          load()
        }}
      />
      <ResetPasswordModal user={resetting} onClose={() => setResetting(null)} />
    </Flex>
  )
}
