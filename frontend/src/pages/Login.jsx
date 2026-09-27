import { useState } from 'react'
import { LockOutlined, MailOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Flex, Form, Input, Typography } from 'antd'
import { api } from '../api'
import { LogoMark } from '../components/Logo'
import { UNIT_COLORS } from '../colors'

const UNITS = [
  { code: 'web', name: 'Web App Development', blurb: 'Client projects, code and delivery' },
  { code: 'training', name: 'Training', blurb: 'Courses, batches and students' },
  { code: 'content', name: 'Academic Content Writing', blurb: 'Research, writing and production' },
]

function BrandPanel() {
  return (
    <div className="login-brand">
      <svg className="login-peaks" viewBox="0 0 800 300" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0 300 L140 150 L230 230 L380 60 L520 210 L610 130 L800 280 L800 300 Z" fill="rgba(255,255,255,0.08)" />
        <path d="M0 300 L200 200 L320 260 L470 150 L640 250 L800 190 L800 300 Z" fill="rgba(255,255,255,0.1)" />
      </svg>
      <Flex align="center" gap={14}>
        <LogoMark size={44} />
        <div>
          <div style={{ fontWeight: 700, fontSize: 22 }}>Yeticode Innovations</div>
          <div style={{ opacity: 0.7, fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase' }}>Staff portal</div>
        </div>
      </Flex>
      <div style={{ marginTop: 'auto', position: 'relative' }}>
        <h1 className="login-headline">One workspace for every team at Yeticode.</h1>
        <p style={{ opacity: 0.8, fontSize: 16, maxWidth: 440 }}>
          Sign in to see the tools and people for your role, in your unit.
        </p>
        <Flex vertical gap={12} style={{ marginTop: 28 }}>
          {UNITS.map((u) => (
            <Flex key={u.code} align="center" gap={12} className="login-unit">
              <span className="login-unit-dot" style={{ background: UNIT_COLORS[u.code].color }} />
              <div>
                <div style={{ fontWeight: 600 }}>{u.name}</div>
                <div style={{ opacity: 0.7, fontSize: 13 }}>{u.blurb}</div>
              </div>
            </Flex>
          ))}
        </Flex>
      </div>
    </div>
  )
}

export default function Login({ onLogin }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleFinish({ username, password }) {
    setBusy(true)
    setError('')
    try {
      const user = await api.login(username.trim(), password)
      await api.ensureCsrf()
      onLogin(user)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <BrandPanel />
      <Flex align="center" justify="center" className="login-form-side">
        <Card variant="borderless" className="login-card">
          <Flex className="login-mobile-logo" align="center" gap={10}>
            <LogoMark size={36} />
            <Typography.Text strong style={{ fontSize: 17 }}>Yeticode Innovations</Typography.Text>
          </Flex>
          <Typography.Title level={2} style={{ marginBottom: 4 }}>Welcome back</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 28 }}>
            Sign in with the email your administrator gave you.
          </Typography.Paragraph>
          {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 20 }} />}
          <Form layout="vertical" requiredMark={false} onFinish={handleFinish} size="large">
            <Form.Item label="Email or username" name="username" rules={[{ required: true, message: 'Enter your email' }]}>
              <Input prefix={<MailOutlined />} placeholder="name@yeticode.com" autoComplete="username" autoFocus />
            </Form.Item>
            <Form.Item label="Password" name="password" rules={[{ required: true, message: 'Enter your password' }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="Your password" autoComplete="current-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={busy} style={{ marginTop: 8, height: 46 }}>
              Sign in
            </Button>
          </Form>
          <Typography.Paragraph type="secondary" style={{ marginTop: 24, fontSize: 13, textAlign: 'center' }}>
            Accounts are created by administrators. There is no self sign-up.
            <br />
            Forgot your password? Ask your unit admin to reset it.
          </Typography.Paragraph>
        </Card>
      </Flex>
    </div>
  )
}
