# Yeticode Innovations internal app

Role-based access for Yeticode's three units. There is no public sign-up:
administrators create every account from the app's **Users** page and give it
one role, and the role decides the person's unit, permissions and dashboard.
Super Admins manage every unit; each unit's senior role (Team Lead, Training
Manager, Production Manager) manages accounts in its own unit only. The Django
admin panel is still there for Super Admins as a fallback.

- `backend/` — Django 5.2 LTS, Django REST Framework, PostgreSQL
- `frontend/` — React 19 + Vite

## Running it locally

### 1. Database

Any PostgreSQL 16 works. The connection comes from `backend/.env` (step 2):
`DJANGO_DATABASE` (database name), `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
With Homebrew on macOS (`brew install postgresql@16 && brew services start postgresql@16`)
you can use your existing `postgres` user and its password.

With Docker instead, `docker compose up -d db` starts one with database, user and
password all set to `yeticode`; put those values in `.env`. Stop any other
PostgreSQL on port 5432 first, or the two will clash.

### 2. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # then set DB_PASSWORD etc.; loaded automatically, git ignores it
python manage.py migrate                # also creates the units, roles and default permissions
python manage.py create_default_users  # Super Admin + one admin per unit (safe to re-run)
python manage.py create_demo_users      # optional, dev only: one account per role
python manage.py runserver              # http://localhost:8000/admin/
```

`create_default_users` makes these accounts if they don't exist yet:

| Username | Role | Unit |
| --- | --- | --- |
| `superadmin` (or `SYSTEM_USERNAME`) | Super Admin | All units, admin panel |
| `web_admin` | Team Lead (manages Web App Development users) | Web App Development |
| `training_admin` | Training Manager (manages Training users) | Training |
| `content_admin` | Production Manager (manages Academic Content Writing users) | Academic Content Writing |

Passwords come from `SYSTEM_USER_PASSWORD` and `UNIT_ADMIN_PASSWORD` in `.env`.
With `DEBUG=TRUE` and no password set, they default to `yeticode@123`; in
production the command refuses to run without them.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                             # http://localhost:5173 (proxies /api and /admin to :8000)
```

Run the backend tests with `python manage.py test accounts` (needs the `CREATEDB` permission above).

## How access works

| Concept | Where it lives |
| --- | --- |
| Units | `Unit` model: Web App Development, Training, Academic Content Writing |
| Roles | `Role` model with a set of capabilities. A role belongs to one unit, or to no unit when it is company-wide (Head HR). |
| Users | `User.role` (one role). `User.unit` is read from the role, so a user can't hold a role from another unit. A database constraint requires a role for everyone except Super Admins. |
| Unit isolation | Unit-scoped roles only ever see their own unit. Cross-unit capabilities (`CROSS_UNIT_CAPABILITIES` in `accounts/rbac.py`) can only be given to company-wide roles; the admin form, the model layer and the API each refuse otherwise. |
| Super Admin | `is_superuser`. The only users allowed into `/admin/`; they have every permission and no role. |
| Capabilities | Django permissions `accounts.<codename>`, defined in `accounts/rbac.py` and checked with `user.has_perm(...)`, or `has_capability(...)` in DRF views. |
| Dashboards | `/api/auth/me/` returns one dashboard widget per capability; the React app renders them. |

The starting capabilities for each role are in `accounts/rbac.py`. They are
applied only when a role is first created, so a Super Admin can change them
afterwards in **Admin → Roles** without a deploy.

### Default capabilities

| Unit | Role | Capabilities |
| --- | --- | --- |
| Web App Development | Junior Web Developer | unit directory, projects, my tasks |
| | Web Developer | unit directory, projects, my tasks |
| | Senior Web Developer | + code reviews |
| | Team Lead | + task assignment, team overview, **user management (own unit)** |
| Training | Student | unit directory, courses, my progress |
| | Instructor | unit directory, courses, my classes, grading |
| | Front Desk Coordinator | unit directory, courses, enquiries, enrollments |
| | Training Manager | unit directory, courses, enquiries, enrollments, batches, training reports, **user management (own unit)** |
| Academic Content Writing | Content Writer | unit directory, my assignments |
| | Content Writer & Research Specialist | + research |
| | Production Manager | unit directory, quality review, production pipeline, **user management (own unit)** |
| | Sales Executive | unit directory, leads & orders |
| | Sales Manager | + sales reports, sales team |
| | HR | unit directory, employee records (Academic Content Writing only) |
| All units | Head HR | employee records, company-wide employee records (everyone in all three units). No admin panel and cannot create accounts. |
| All units | Super Admin | everything: users in all units, roles and permissions (in the app), plus the Django admin panel |

The unit directory and the company-wide directory are working features today; the other dashboard
cards are placeholders for the features each unit will need.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/auth/csrf/` | Sets the CSRF cookie |
| `POST /api/auth/login/` | Session login, returns the current user |
| `POST /api/auth/logout/` | Ends the session |
| `GET /api/auth/me/` | Current user, unit, role, capabilities, dashboard |
| `GET /api/unit/members/` | People in your unit (needs `view_unit_directory`) |
| `GET /api/company/members/` | Everyone in every unit (company-wide roles with `view_all_employee_records`) |
| `GET/POST /api/manage/users/`, `GET/PATCH /api/manage/users/<id>/` | List, create, edit, deactivate and reset passwords. Super Admins: all users. `manage_unit_users`: own unit, own unit's roles only. No DELETE; deactivate instead. |
| `GET /api/manage/roles/`, `PATCH /api/manage/roles/<id>/` | List roles (unit admins see their unit's); Super Admins edit a role's `capabilities` |
| `GET /api/manage/capabilities/` | The capability catalog (Super Admins) |
