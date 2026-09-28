import { useState } from 'react'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Flex, Form, Input, Typography } from 'antd'
import { api } from '../api'
import { LogoMark } from '../components/Logo'
import { useBranding } from '../branding'
// The sign-in page is public, so it stays neutral: no internal team names.
function BrandPanel() {
  const { branding } = useBranding()
  return (
    <div className="login-brand">
      <svg className="login-peaks" viewBox="0 0 800 300" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0 300 L140 150 L230 230 L380 60 L520 210 L610 130 L800 280 L800 300 Z" fill="rgba(255,255,255,0.08)" />
        <path d="M0 300 L200 200 L320 260 L470 150 L640 250 L800 190 L800 300 Z" fill="rgba(255,255,255,0.1)" />
      </svg>
      <Flex align="center" gap={14}>
        <LogoMark size={44} />
        <div>
          <div style={{ fontWeight: 700, fontSize: 22 }}>{branding.name}</div>
          {branding.tagline && (
            <div style={{ opacity: 0.7, fontSize: 13, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              {branding.tagline}
            </div>
          )}
        </div>
      </Flex>
      <div style={{ marginTop: 'auto', position: 'relative' }}>
        <h1 className="login-headline">Welcome to your staff portal.</h1>
        <p style={{ opacity: 0.8, fontSize: 16, maxWidth: 440, marginBottom: 0 }}>
          Sign in to reach your team, your work and your requests, all in one place.
        </p>
      </div>
    </div>
  )
}

export default function Login({ onLogin }) {
  const { branding } = useBranding()
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
            <Typography.Text strong style={{ fontSize: 17 }}>{branding.name}</Typography.Text>
          </Flex>
          <Typography.Title level={2} style={{ marginBottom: 4 }}>Welcome back</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 28 }}>
            Sign in with your username{branding.domain ? ` (or username@${branding.domain})` : ''} or your email.
          </Typography.Paragraph>
          {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 20 }} />}
          <Form layout="vertical" requiredMark={false} onFinish={handleFinish} size="large">
            <Form.Item label="Username or email" name="username" rules={[{ required: true, message: 'Enter your username or email' }]}>
              <Input
                prefix={<UserOutlined />}
                placeholder={branding.domain ? `abhishekojha or abhishekojha@${branding.domain}` : 'abhishekojha or your email'}
                autoComplete="username"
                autoFocus
              />
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
            Forgot your password? Ask your administrator to reset it.
          </Typography.Paragraph>
        </Card>
      </Flex>
    </div>
  )
}
