import { CompanyDirectory, UnitDirectory } from './widgets'

function LinkTo({ page, label }) {
  return (
    <a className="button" href={`#${page}`}>
      {label}
    </a>
  )
}

// Widgets with a real implementation; every other capability shows a placeholder card.
const WIDGETS = {
  view_unit_directory: UnitDirectory,
  view_all_employee_records: CompanyDirectory,
  manage_unit_users: () => <LinkTo page="users" label="Manage users" />,
  manage_users: () => <LinkTo page="users" label="Manage users" />,
  manage_roles: () => <LinkTo page="roles" label="Edit roles" />,
}

// Widgets that show a table and take the full width.
const WIDE = new Set(['view_unit_directory', 'view_all_employee_records'])

function Placeholder() {
  return <p className="muted small">Coming soon.</p>
}

export default function Dashboard({ user }) {
  const scope = user.is_super_admin
    ? 'Super Admin · All units'
    : `${user.role.name} · ${user.unit ? user.unit.name : 'All units'}`

  return (
    <>
      <h1>Welcome, {user.full_name || user.username}</h1>
      <p className="badge">{scope}</p>
      {user.dashboard.length === 0 && (
        <p className="muted">Your role has no dashboard sections yet. Ask an administrator.</p>
      )}
      <section className="grid">
        {user.dashboard.map((widget) => {
          const Body = WIDGETS[widget.key] ?? Placeholder
          return (
            <article key={widget.key} className={`card ${WIDE.has(widget.key) ? 'wide' : ''}`}>
              <h2>{widget.title}</h2>
              <p className="muted">{widget.description}</p>
              <Body user={user} />
            </article>
          )
        })}
      </section>
      {user.is_super_admin && (
        <p className="muted small footnote">
          Need something the app doesn't cover yet? The <a href="/admin/">Django admin panel</a> is
          still available to Super Admins.
        </p>
      )}
    </>
  )
}
