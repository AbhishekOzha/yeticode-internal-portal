import { useEffect, useState } from 'react'
import { api } from './api'
import Dashboard from './Dashboard'
import Login from './Login'
import RolesPage from './RolesPage'
import UsersPage from './UsersPage'

function pagesFor(user) {
  const pages = [{ key: 'dashboard', label: 'Dashboard', Component: Dashboard }]
  if (user.can_manage_users) pages.push({ key: 'users', label: 'Users', Component: UsersPage })
  if (user.can_manage_roles) pages.push({ key: 'roles', label: 'Roles & permissions', Component: RolesPage })
  return pages
}

function usePageFromHash() {
  const [page, setPage] = useState(() => window.location.hash.slice(1) || 'dashboard')
  useEffect(() => {
    const onHashChange = () => setPage(window.location.hash.slice(1) || 'dashboard')
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  return page
}

export default function App() {
  const [user, setUser] = useState(undefined) // undefined = still checking the session
  const pageKey = usePageFromHash()

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

  if (user === undefined) return <p className="loading">Loading…</p>
  if (!user) return <Login onLogin={setUser} />

  const pages = pagesFor(user)
  const page = pages.find((p) => p.key === pageKey) ?? pages[0]

  return (
    <div className="layout">
      <header className="topbar">
        <strong>Yeticode Innovations</strong>
        {pages.length > 1 && (
          <nav className="tabs">
            {pages.map((p) => (
              <a key={p.key} href={`#${p.key}`} className={p.key === page.key ? 'active' : ''}>
                {p.label}
              </a>
            ))}
          </nav>
        )}
        <div className="topbar-right">
          <span className="muted">{user.full_name || user.username}</span>
          <button className="secondary" onClick={handleLogout}>Sign out</button>
        </div>
      </header>
      <main className="content">
        <page.Component user={user} />
      </main>
    </div>
  )
}
