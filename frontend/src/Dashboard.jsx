import { UnitDirectory } from './widgets'

// Widgets with a real implementation; every other capability shows a placeholder card.
const WIDGETS = {
  view_unit_directory: UnitDirectory,
  admin_panel: AdminPanel,
}

function AdminPanel() {
  return (
    <a className="button" href="/admin/">
      Open the admin panel
    </a>
  )
}

function Placeholder() {
  return <p className="muted small">Coming soon.</p>
}

export default function Dashboard({ user, onLogout }) {
  const scope = user.is_super_admin
    ? 'Super Admin · All units'
    : `${user.role.name} · ${user.unit.name}`

  return (
    <div className="layout">
      <header className="topbar">
        <strong>Yeticode Innovations</strong>
        <div className="topbar-right">
          <span className="muted">{user.full_name || user.username}</span>
          <button className="secondary" onClick={onLogout}>Sign out</button>
        </div>
      </header>
      <main className="content">
        <h1>Welcome, {user.full_name || user.username}</h1>
        <p className="badge">{scope}</p>
        {user.dashboard.length === 0 && (
          <p className="muted">Your role has no dashboard sections yet. Ask an administrator.</p>
        )}
        <section className="grid">
          {user.dashboard.map((widget) => {
            const Body = WIDGETS[widget.key] ?? Placeholder
            return (
              <article key={widget.key} className={`card ${widget.key === 'view_unit_directory' ? 'wide' : ''}`}>
                <h2>{widget.title}</h2>
                <p className="muted">{widget.description}</p>
                <Body user={user} />
              </article>
            )
          })}
        </section>
      </main>
    </div>
  )
}
