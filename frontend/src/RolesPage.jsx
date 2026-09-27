import { useEffect, useMemo, useState } from 'react'
import { api } from './api'

function RoleCard({ role, capabilities, onSaved }) {
  const [selected, setSelected] = useState(new Set(role.capabilities))
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const companyWide = role.unit_id === null
  const dirty =
    selected.size !== role.capabilities.length || role.capabilities.some((c) => !selected.has(c))

  function toggle(code) {
    setMessage('')
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  async function save() {
    setBusy(true)
    setError('')
    try {
      const ordered = capabilities.map((c) => c.code).filter((code) => selected.has(code))
      const updated = await api.updateRole(role.id, { capabilities: ordered })
      onSaved(updated)
      setMessage('Saved.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="card">
      <div className="role-header">
        <h2>{role.name}</h2>
        <span className="muted small">
          {role.member_count} active {role.member_count === 1 ? 'user' : 'users'}
        </span>
      </div>
      <ul className="capability-list">
        {capabilities.map((cap) => {
          const blocked = cap.cross_unit && !companyWide
          return (
            <li key={cap.code}>
              <label className={`checkbox ${blocked ? 'disabled' : ''}`} title={blocked ? 'Only company-wide roles can see across units.' : cap.description}>
                <input
                  type="checkbox"
                  checked={selected.has(cap.code)}
                  disabled={blocked}
                  onChange={() => toggle(cap.code)}
                />
                {cap.label}
              </label>
            </li>
          )
        })}
      </ul>
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button onClick={save} disabled={!dirty || busy}>{busy ? 'Saving…' : 'Save'}</button>
        {message && !dirty && <span className="muted small">{message}</span>}
      </div>
    </article>
  )
}

export default function RolesPage() {
  const [roles, setRoles] = useState(null)
  const [capabilities, setCapabilities] = useState([])
  const [error, setError] = useState('')
  const [unit, setUnit] = useState('')

  useEffect(() => {
    Promise.all([api.listRoles(), api.listCapabilities()])
      .then(([r, c]) => {
        setRoles(r)
        setCapabilities(c)
        setUnit(r[0]?.unit ?? '')
      })
      .catch((err) => setError(err.message))
  }, [])

  const units = useMemo(() => [...new Set((roles ?? []).map((r) => r.unit))], [roles])

  function handleSaved(updated) {
    setRoles((current) => current.map((r) => (r.id === updated.id ? updated : r)))
  }

  if (error) return <p className="error">{error}</p>
  if (!roles) return <p className="muted">Loading…</p>

  return (
    <>
      <h1>Roles & permissions</h1>
      <p className="muted">
        Choose what each role can see and do. Changes apply to everyone with that role the next
        time they load the app. Cross-unit permissions are only available to company-wide roles.
      </p>
      <nav className="tabs sub-tabs">
        {units.map((u) => (
          <button key={u} className={u === unit ? 'active' : ''} onClick={() => setUnit(u)}>
            {u}
          </button>
        ))}
      </nav>
      <section className="grid">
        {roles
          .filter((r) => r.unit === unit)
          .map((role) => (
            <RoleCard key={role.id} role={role} capabilities={capabilities} onSaved={handleSaved} />
          ))}
      </section>
    </>
  )
}
