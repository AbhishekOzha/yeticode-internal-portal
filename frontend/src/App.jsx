import { useEffect, useState } from 'react'
import { api } from './api'
import Dashboard from './Dashboard'
import Login from './Login'

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
    setUser(null)
  }

  if (user === undefined) return <p className="loading">Loading…</p>
  if (!user) return <Login onLogin={setUser} />
  return <Dashboard user={user} onLogout={handleLogout} />
}
