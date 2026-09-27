import { useEffect, useState } from 'react'
import { api } from './api'

function MemberTable({ load, showUnit = false }) {
  const [members, setMembers] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    load().then(setMembers).catch((err) => setError(err.message))
  }, [load])

  if (error) return <p className="error">{error}</p>
  if (!members) return <p className="muted small">Loading…</p>
  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          {showUnit && <th>Unit</th>}
          <th>Role</th>
          <th>Email</th>
        </tr>
      </thead>
      <tbody>
        {members.map((m) => (
          <tr key={m.id}>
            <td>{m.full_name || m.username}</td>
            {showUnit && <td>{m.unit}</td>}
            <td>{m.role}</td>
            <td>{m.email}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function UnitDirectory() {
  return <MemberTable load={api.unitMembers} />
}

export function CompanyDirectory() {
  return <MemberTable load={api.companyMembers} showUnit />
}
