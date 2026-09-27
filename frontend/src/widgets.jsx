import { useEffect, useState } from 'react'
import { api } from './api'

export function UnitDirectory() {
  const [members, setMembers] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.unitMembers().then(setMembers).catch((err) => setError(err.message))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!members) return <p className="muted small">Loading…</p>
  return (
    <table>
      <thead>
        <tr><th>Name</th><th>Role</th><th>Email</th></tr>
      </thead>
      <tbody>
        {members.map((m) => (
          <tr key={m.id}>
            <td>{m.full_name || m.username}</td>
            <td>{m.role}</td>
            <td>{m.email}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
