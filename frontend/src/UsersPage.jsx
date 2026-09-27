import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api'

const SUPER_ADMIN = 'super_admin'
const EMPTY_FORM = {
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  role: '',
  password: '',
  is_active: true,
}

function formFromUser(user) {
  return {
    username: user.username,
    first_name: user.first_name,
    last_name: user.last_name,
    email: user.email,
    role: user.is_super_admin ? SUPER_ADMIN : String(user.role ?? ''),
    password: '',
    is_active: user.is_active,
  }
}

function payloadFromForm(form, isNew) {
  const payload = {
    username: form.username.trim(),
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    email: form.email.trim(),
    is_active: form.is_active,
  }
  if (form.role === SUPER_ADMIN) {
    payload.is_super_admin = true
    payload.role = null
  } else {
    payload.is_super_admin = false
    payload.role = form.role ? Number(form.role) : null
  }
  if (isNew || form.password) payload.password = form.password
  return payload
}

function UserForm({ user, roles, currentUser, onSaved, onCancel }) {
  const isNew = !user
  const isSelf = user?.id === currentUser.id
  const [form, setForm] = useState(isNew ? EMPTY_FORM : formFromUser(user))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const rolesByUnit = useMemo(() => {
    const groups = new Map()
    for (const role of roles) {
      if (!groups.has(role.unit)) groups.set(role.unit, [])
      groups.get(role.unit).push(role)
    }
    return [...groups.entries()]
  }, [roles])

  const set = (field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = payloadFromForm(form, isNew)
      const saved = isNew ? await api.createUser(payload) : await api.updateUser(user.id, payload)
      onSaved(saved)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card form" onSubmit={handleSubmit}>
      <h2>{isNew ? 'Add a user' : `Edit ${user.username}`}</h2>
      <div className="form-grid">
        <label>
          Username
          <input value={form.username} onChange={set('username')} required />
        </label>
        <label>
          Email
          <input type="email" value={form.email} onChange={set('email')} />
        </label>
        <label>
          First name
          <input value={form.first_name} onChange={set('first_name')} />
        </label>
        <label>
          Last name
          <input value={form.last_name} onChange={set('last_name')} />
        </label>
        <label>
          Role
          <select value={form.role} onChange={set('role')} required disabled={isSelf}>
            <option value="">Choose a role…</option>
            {currentUser.is_super_admin && <option value={SUPER_ADMIN}>Super Admin (all units)</option>}
            {rolesByUnit.map(([unit, unitRoles]) => (
              <optgroup key={unit} label={unit}>
                {unitRoles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label>
          {isNew ? 'Password' : 'New password (leave empty to keep)'}
          <input
            type="password"
            value={form.password}
            onChange={set('password')}
            autoComplete="new-password"
            required={isNew}
          />
        </label>
      </div>
      {!isNew && !isSelf && (
        <label className="checkbox">
          <input type="checkbox" checked={form.is_active} onChange={set('is_active')} />
          Active (unticked users cannot sign in)
        </label>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="actions">
        <button type="submit" disabled={busy}>{busy ? 'Saving…' : isNew ? 'Create user' : 'Save changes'}</button>
        <button type="button" className="secondary" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

export default function UsersPage({ user: currentUser }) {
  const [users, setUsers] = useState(null)
  const [roles, setRoles] = useState([])
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null) // null = closed, 'new', or a user
  const [query, setQuery] = useState('')
  const [unitFilter, setUnitFilter] = useState('')
  const [showInactive, setShowInactive] = useState(false)

  const load = useCallback(() => {
    Promise.all([api.listUsers(), api.listRoles()])
      .then(([u, r]) => {
        setUsers(u)
        setRoles(r)
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(load, [load])

  const units = useMemo(() => [...new Set((users ?? []).map((u) => u.unit))], [users])

  const visible = (users ?? []).filter((u) => {
    if (!showInactive && !u.is_active) return false
    if (unitFilter && u.unit !== unitFilter) return false
    const text = `${u.username} ${u.first_name} ${u.last_name} ${u.email} ${u.role_name ?? ''}`.toLowerCase()
    return text.includes(query.trim().toLowerCase())
  })

  async function toggleActive(target) {
    try {
      await api.updateUser(target.id, { is_active: !target.is_active })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  function handleSaved() {
    setEditing(null)
    load()
  }

  const scope = currentUser.is_super_admin ? 'all units' : currentUser.unit.name

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Users</h1>
          <p className="muted">Accounts in {scope}. Only administrators can create accounts.</p>
        </div>
        {editing === null && <button onClick={() => setEditing('new')}>Add user</button>}
      </div>

      {editing !== null && (
        <UserForm
          key={editing === 'new' ? 'new' : editing.id}
          user={editing === 'new' ? null : editing}
          roles={roles}
          currentUser={currentUser}
          onSaved={handleSaved}
          onCancel={() => setEditing(null)}
        />
      )}

      {error && <p className="error" role="alert">{error}</p>}

      <div className="toolbar">
        <input
          className="search"
          placeholder="Search by name, username, email or role"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {units.length > 1 && (
          <select value={unitFilter} onChange={(e) => setUnitFilter(e.target.value)}>
            <option value="">All units</option>
            {units.map((unit) => (
              <option key={unit} value={unit}>{unit}</option>
            ))}
          </select>
        )}
        <label className="checkbox">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Show deactivated
        </label>
      </div>

      {!users ? (
        <p className="muted">Loading…</p>
      ) : (
        <div className="card table-card">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Username</th>
                <th>Unit</th>
                <th>Role</th>
                <th>Status</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {visible.map((u) => (
                <tr key={u.id} className={u.is_active ? '' : 'inactive'}>
                  <td>{`${u.first_name} ${u.last_name}`.trim() || '—'}</td>
                  <td>{u.username}</td>
                  <td>{u.unit}</td>
                  <td>{u.is_super_admin ? 'Super Admin' : u.role_name}</td>
                  <td>{u.is_active ? 'Active' : 'Deactivated'}</td>
                  <td className="row-actions">
                    <button className="link" onClick={() => setEditing(u)}>Edit</button>
                    {u.id !== currentUser.id && (
                      <button className="link" onClick={() => toggleActive(u)}>
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">No users match.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
