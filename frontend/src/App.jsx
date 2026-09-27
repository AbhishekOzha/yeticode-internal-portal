import { useEffect, useState } from 'react'
import {
  AppstoreOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MoonOutlined,
  SafetyCertificateOutlined,
  SunOutlined,
  TeamOutlined,
  UsergroupAddOutlined,
} from '@ant-design/icons'
import { Button, Dropdown, Flex, Layout, Menu, Spin, Tooltip, Typography, Grid } from 'antd'
import { api } from './api'
import { Logo } from './components/Logo'
import { PersonAvatar } from './components/People'
import { displayName } from './people'
import Dashboard from './pages/Dashboard'
import Directory from './pages/Directory'
import Login from './pages/Login'
import Roles from './pages/Roles'
import Users from './pages/Users'
import { useThemeMode } from './themeMode'

const { Sider, Header, Content } = Layout

function pagesFor(user) {
  const pages = [{ key: 'dashboard', label: 'Dashboard', icon: <AppstoreOutlined />, Component: Dashboard }]
  const directory = user.capabilities.includes('view_all_employee_records')
    ? 'Company directory'
    : user.capabilities.includes('view_unit_directory') && !user.is_super_admin
      ? 'Team directory'
      : null
  if (directory) pages.push({ key: 'directory', label: directory, icon: <TeamOutlined />, Component: Directory })
  if (user.can_manage_users) pages.push({ key: 'users', label: 'Users', icon: <UsergroupAddOutlined />, Component: Users })
  if (user.can_manage_roles)
    pages.push({ key: 'roles', label: 'Roles & permissions', icon: <SafetyCertificateOutlined />, Component: Roles })
  return pages
}

function useHashPage() {
  const read = () => window.location.hash.slice(1) || 'dashboard'
  const [page, setPage] = useState(read)
  useEffect(() => {
    const onChange = () => setPage(read())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return page
}

function scopeLabel(user) {
  if (user.is_super_admin) return 'Super Admin · All units'
  return `${user.role.name} · ${user.unit ? user.unit.name : 'All units'}`
}

function Shell({ user, onLogout }) {
  const { dark, toggle } = useThemeMode()
  const screens = Grid.useBreakpoint()
  const [collapsed, setCollapsed] = useState(false)
  const pages = pagesFor(user)
  const pageKey = useHashPage()
  const page = pages.find((p) => p.key === pageKey) ?? pages[0]
  const narrow = !screens.lg

  const menu = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[page.key]}
      items={pages.map((p) => ({ key: p.key, icon: p.icon, label: p.label }))}
      onClick={({ key }) => {
        window.location.hash = key
        if (narrow) setCollapsed(true)
      }}
      style={{ borderInlineEnd: 0, padding: '0 10px' }}
    />
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={256}
        collapsedWidth={narrow ? 0 : 80}
        collapsible
        collapsed={collapsed}
        trigger={null}
        breakpoint="lg"
        onBreakpoint={(broken) => setCollapsed(broken)}
        style={{ position: narrow ? 'fixed' : 'sticky', top: 0, left: 0, height: '100vh', zIndex: 30 }}
      >
        <div style={{ padding: '18px 20px 22px' }}>
          <Logo collapsed={collapsed && !narrow} />
        </div>
        {menu}
        {!collapsed && (
          <div className="sider-footer">
            <Typography.Text style={{ color: 'rgba(226,232,255,0.55)', fontSize: 12 }}>
              Signed in as
            </Typography.Text>
            <Typography.Text style={{ color: '#fff', display: 'block', fontSize: 13 }} ellipsis>
              {scopeLabel(user)}
            </Typography.Text>
          </div>
        )}
      </Sider>
      {narrow && !collapsed && <div className="sider-mask" onClick={() => setCollapsed(true)} />}
      <Layout>
        <Header className="app-header">
          <Flex align="center" gap={12}>
            <Button
              type="text"
              aria-label={collapsed ? 'Open menu' : 'Close menu'}
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed((c) => !c)}
            />
            <Typography.Title level={4} style={{ margin: 0 }}>
              {page.label}
            </Typography.Title>
          </Flex>
          <Flex align="center" gap={8}>
            <Tooltip title={dark ? 'Light mode' : 'Dark mode'}>
              <Button type="text" shape="circle" aria-label="Toggle theme" icon={dark ? <SunOutlined /> : <MoonOutlined />} onClick={toggle} />
            </Tooltip>
            <Dropdown
              trigger={['click']}
              menu={{
                items: [
                  {
                    key: 'who',
                    disabled: true,
                    label: (
                      <div style={{ padding: '4px 0' }}>
                        <div style={{ fontWeight: 600, color: 'var(--ant-color-text)' }}>{displayName(user)}</div>
                        <div style={{ fontSize: 12 }}>{scopeLabel(user)}</div>
                      </div>
                    ),
                  },
                  { type: 'divider' },
                  { key: 'logout', icon: <LogoutOutlined />, label: 'Sign out', danger: true },
                ],
                onClick: ({ key }) => key === 'logout' && onLogout(),
              }}
            >
              <Button type="text" className="user-button">
                <PersonAvatar person={user} size={32} />
                {screens.md && <span className="user-button-name">{displayName(user)}</span>}
              </Button>
            </Dropdown>
          </Flex>
        </Header>
        <Content className="app-content">
          <page.Component user={user} />
        </Content>
      </Layout>
    </Layout>
  )
}

export default function App() {
  const [user, setUser] = useState(undefined) // undefined = still checking the session

  useEffect(() => {
    api
      .ensureCsrf()
      .then(api.me)
      .then(setUser)
      .catch(() => setUser(null))
  }, [])

  async function handleLogout() {
    await api.logout()
    // Django rotates the CSRF token on login/logout; fetch a fresh one.
    await api.ensureCsrf()
    window.location.hash = ''
    setUser(null)
  }

  if (user === undefined) {
    return (
      <Flex align="center" justify="center" style={{ minHeight: '100vh' }}>
        <Spin size="large" />
      </Flex>
    )
  }
  if (!user) return <Login onLogin={setUser} />
  return <Shell user={user} onLogout={handleLogout} />
}
