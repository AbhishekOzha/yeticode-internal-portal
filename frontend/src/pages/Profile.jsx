import { useState } from 'react'
import { CameraOutlined, DeleteOutlined, EditOutlined, LockOutlined, MailOutlined, PlusOutlined } from '@ant-design/icons'
import { App, Button, Card, Col, Descriptions, Flex, Form, Input, Popconfirm, Row, Tag, Typography, Upload } from 'antd'
import { api, fileForm } from '../api'
import { PersonAvatar, UnitTag } from '../components/People'
import { displayName } from '../people'
import { IMAGE_ACCEPT, imageProblem } from '../uploads'

function PhotoCard({ user, onUserChange }) {
  const { message } = App.useApp()
  const [busy, setBusy] = useState(false)

  async function save(data, success) {
    setBusy(true)
    try {
      onUserChange(await api.updateProfile(data))
      message.success(success)
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  function upload(file) {
    const problem = imageProblem(file)
    if (problem) message.error(problem)
    else save(fileForm('avatar', file), 'Photo updated.')
    return Upload.LIST_IGNORE
  }

  return (
    <Card style={{ height: '100%' }}>
      <Flex vertical align="center" gap={14} style={{ textAlign: 'center', padding: '8px 0' }}>
        <PersonAvatar person={user} size={112} />
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {displayName(user)}
          </Typography.Title>
          <Typography.Text type="secondary">{user.email}</Typography.Text>
        </div>
        <Flex gap={8} wrap justify="center">
          {user.is_super_admin ? (
            <Tag color="gold" variant="filled" style={{ marginInlineEnd: 0 }}>Super Admin</Tag>
          ) : (
            <Tag variant="filled" style={{ marginInlineEnd: 0 }}>{user.role.name}</Tag>
          )}
          <UnitTag code={user.unit?.code} name={user.unit ? user.unit.name : 'All units'} />
        </Flex>
        <Flex gap={8} wrap justify="center" style={{ marginTop: 6 }}>
          <Upload accept={IMAGE_ACCEPT} showUploadList={false} beforeUpload={upload}>
            <Button type="primary" icon={<CameraOutlined />} loading={busy}>
              {user.avatar ? 'Change photo' : 'Upload photo'}
            </Button>
          </Upload>
          {user.avatar && (
            <Popconfirm title="Remove your photo?" okText="Remove" onConfirm={() => save({ avatar: null }, 'Photo removed.')}>
              <Button icon={<DeleteOutlined />} disabled={busy}>
                Remove
              </Button>
            </Popconfirm>
          )}
        </Flex>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          PNG, JPG or WebP, up to 2 MB. A square photo looks best.
        </Typography.Text>
      </Flex>
    </Card>
  )
}

function SecondaryEmail({ user, onUserChange }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)

  async function save(secondary_email) {
    setBusy(true)
    try {
      onUserChange(await api.updateProfile({ secondary_email }))
      message.success(secondary_email ? 'Secondary email saved.' : 'Secondary email removed.')
      setEditing(false)
    } catch (err) {
      const errors = err.data?.secondary_email
      if (errors) form.setFields([{ name: 'secondary_email', errors: [].concat(errors) }])
      else message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (editing) {
    return (
      <Form
        form={form}
        layout="inline"
        initialValues={{ secondary_email: user.secondary_email }}
        onFinish={({ secondary_email }) => save(secondary_email.trim())}
        style={{ rowGap: 8 }}
      >
        <Form.Item
          name="secondary_email"
          rules={[{ required: true, type: 'email', message: 'Enter a valid email address' }]}
          style={{ flex: '1 1 240px' }}
        >
          <Input prefix={<MailOutlined />} placeholder="you@example.com" autoFocus autoComplete="email" />
        </Form.Item>
        <Flex gap={8}>
          <Button type="primary" htmlType="submit" loading={busy}>
            Save
          </Button>
          <Button onClick={() => setEditing(false)}>Cancel</Button>
        </Flex>
      </Form>
    )
  }

  if (!user.secondary_email) {
    return (
      <Button icon={<PlusOutlined />} onClick={() => setEditing(true)}>
        Add secondary email
      </Button>
    )
  }

  return (
    <Flex align="center" gap={8} wrap>
      <Typography.Text>{user.secondary_email}</Typography.Text>
      <Button size="small" type="text" icon={<EditOutlined />} aria-label="Edit secondary email" onClick={() => setEditing(true)} />
      <Popconfirm title="Remove your secondary email?" okText="Remove" onConfirm={() => save('')}>
        <Button size="small" type="text" danger icon={<DeleteOutlined />} aria-label="Remove secondary email" loading={busy} />
      </Popconfirm>
    </Flex>
  )
}

export default function Profile({ user, onUserChange }) {
  const details = [
    { key: 'name', label: 'Full name', children: displayName(user) },
    { key: 'username', label: 'Username', children: <span className="mono">{user.login}</span> },
    { key: 'role', label: 'Role', children: user.is_super_admin ? 'Super Admin' : user.role.name },
    { key: 'unit', label: 'Unit', children: user.unit ? user.unit.name : 'All units' },
    {
      key: 'last_login',
      label: 'Last sign-in',
      children: user.last_login ? new Date(user.last_login).toLocaleString() : 'Now',
    },
  ].filter(Boolean)

  return (
    <Flex vertical gap={20}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          My profile
        </Typography.Title>
        <Typography.Text type="secondary">
          Your photo appears in the header, in directories and on the Users page.
        </Typography.Text>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <PhotoCard user={user} onUserChange={onUserChange} />
        </Col>
        <Col xs={24} lg={16}>
          <Flex vertical gap={16}>
            <Card title="Email addresses">
              <Flex vertical gap={20}>
                <div>
                  <Typography.Text type="secondary" className="cap-group-label">
                    Primary email
                  </Typography.Text>
                  <Flex align="center" gap={8} wrap style={{ marginTop: 6 }}>
                    <Typography.Text strong>{user.email || '—'}</Typography.Text>
                    <Tag icon={<LockOutlined />} variant="filled" style={{ marginInlineEnd: 0 }}>
                      Sign-in email
                    </Tag>
                  </Flex>
                  <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                    You sign in with this address. It can't be removed, and only an administrator can change it.
                  </Typography.Text>
                </div>
                <div>
                  <Typography.Text type="secondary" className="cap-group-label">
                    Secondary email
                  </Typography.Text>
                  <div style={{ marginTop: 6 }}>
                    <SecondaryEmail user={user} onUserChange={onUserChange} />
                  </div>
                </div>
              </Flex>
            </Card>
            <Card title="Your details">
              <Descriptions column={{ xs: 1, md: 2 }} items={details} />
              <Typography.Text type="secondary" style={{ fontSize: 13, display: 'block', marginTop: 12 }}>
                To change your name or role, ask {user.is_super_admin ? 'another Super Admin' : 'your unit admin'}.
              </Typography.Text>
            </Card>
          </Flex>
        </Col>
      </Row>
    </Flex>
  )
}
