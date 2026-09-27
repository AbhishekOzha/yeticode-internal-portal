import { useEffect, useState } from 'react'
import {
  AppstoreOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  LogoutOutlined,
  MessageOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MoonOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  StarOutlined,
  SunOutlined,
  TeamOutlined,
  UserOutlined,
  UsergroupAddOutlined,
  WalletOutlined,
} from '@ant-design/icons'
import { Badge, Button, Dropdown, Flex, Layout, Menu, Spin, Tooltip, Typography, Grid } from 'antd'
import { api } from './api'
import { CallProvider } from './components/CallProvider'
import { ChatProvider } from './components/ChatProvider'
import { Logo } from './components/Logo'
import { NotificationBell } from './components/NotificationBell'
import { OfficeReminders } from './components/OfficeReminders'
import { PersonAvatar } from './components/People'
import { displayName } from './people'
import Chat from './pages/Chat'
import CompanySettings from './pages/CompanySettings'
import Dashboard from './pages/Dashboard'
import Directory from './pages/Directory'
import Leave from './pages/Leave'
import Login from './pages/Login'
import OfficeHours from './pages/OfficeHours'
import Payroll from './pages/Payroll'
import { canManagePayroll } from './payroll'
import Profile from './pages/Profile'
import Reviews from './pages/Reviews'
import Roles from './pages/Roles'
import Users from './pages/Users'
import { canApproveLeave, canManageOfficeHours, canReadReviews, inTeam, useChat } from './team'
import { useThemeMode } from './themeMode'

const { Sider, Header, Content } = Layout

// Pages that belong to one unit are grouped under it in the sidebar, so they
// don't read as company-wide.
const CONTENT_SECTION = { key: 'section-content', label: 'Academic Content Writing', icon: <FileTextOutlined /> }

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
  if (user.is_super_admin)
    pages.push({ key: 'company', label: 'Company settings', icon: <SettingOutlined />, Component: CompanySettings })
  const content = CONTENT_SECTION
  if (inTeam(user)) pages.push({ key: 'chat', label: 'Team chat', icon: <MessageOutlined />, Component: Chat, section: content })
  if (inTeam(user) || canApproveLeave(user))
    pages.push({ key: 'leave', label: 'Leave', icon: <CalendarOutlined />, Component: Leave, section: content })
  if (inTeam(user) || canReadReviews(user))
    pages.push({ key: 'reviews', label: 'Reviews', icon: <StarOutlined />, Component: Reviews, section: content })
  if (canManageOfficeHours(user))
    pages.push({
      key: 'office-hours',
      label: 'Office hours',
      icon: <ClockCircleOutlined />,
      Component: OfficeHours,
      section: content,
    })
  if (canManagePayroll(user))
    pages.push({ key: 'payroll', label: 'Payroll', icon: <WalletOutlined />, Component: Payroll, section: content })
  // Reached from the user menu rather than the sidebar.
  pages.push({ key: 'profile', label: 'My profile', icon: <UserOutlined />, Component: Profile, hidden: true })
  return pages
}

// Sidebar items: top-level pages, with each unit's pages nested under the unit's name.
function menuItems(pages, totalUnread) {
  const item = (p) => ({
    key: p.key,
    icon: p.icon,
    label:
      p.key === 'chat' && totalUnread ? (
        <Flex justify="space-between" align="center">
          {p.label}
          <Badge count={totalUnread} size="small" />
        </Flex>
      ) : (
        p.label
      ),
  })
  const items = []
  for (const p of pages.filter((x) => !x.hidden)) {
    if (!p.section) {
      items.push(item(p))
      continue
    }
    let group = items.find((i) => i.key === p.section.key)
    if (!group) {
      group = { key: p.section.key, icon: p.section.icon, label: p.section.label, children: [] }
      items.push(group)
    }
    group.children.push(item(p))
  }
  // Show unread chat messages on the section too, so they're visible when it's folded.
  for (const group of items.filter((i) => i.children)) {
    if (totalUnread && group.children.some((c) => c.key === 'chat')) {
      group.label = (
        <Flex justify="space-between" align="center">
          {group.label}
          <Badge count={totalUnread} size="small" />
        </Flex>
      )
    }
  }
  return items
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

function Shell({ user, onUserChange, onLogout }) {
  const { dark, toggle } = useThemeMode()
  const { totalUnread } = useChat()
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
      defaultOpenKeys={[CONTENT_SECTION.key]}
      items={menuItems(pages, totalUnread)}
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
              {page.section && (
                <Typography.Text type="secondary" className="header-section">
                  {page.section.label} /{' '}
                </Typography.Text>
              )}
              {page.label}
            </Typography.Title>
          </Flex>
          <Flex align="center" gap={8}>
            <NotificationBell />
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
                  { key: 'profile', icon: <UserOutlined />, label: 'My profile' },
                  ...(user.is_super_admin ? [{ key: 'company', icon: <SettingOutlined />, label: 'Company settings' }] : []),
                  { type: 'divider' },
                  { key: 'logout', icon: <LogoutOutlined />, label: 'Sign out', danger: true },
                ],
                onClick: ({ key }) => {
                  if (key === 'logout') onLogout()
                  else window.location.hash = key
                },
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
          <page.Component user={user} onUserChange={onUserChange} />
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
  return (
    <ChatProvider key={user.id} user={user}>
      <OfficeReminders user={user} />
      <CallProvider>
        <Shell user={user} onUserChange={setUser} onLogout={handleLogout} />
      </CallProvider>
    </ChatProvider>
  )
}
