# Yeticode Innovations internal app

Role-based access for Yeticode's three units. There is no public sign-up:
a Super Admin creates every account in the Django admin and gives it one role,
and the role decides the person's unit, permissions and dashboard.

- `backend/` — Django 5.1, Django REST Framework, PostgreSQL
- `frontend/` — React 19 + Vite

## Running it locally

```bash
docker compose up -d db                 # or use any PostgreSQL 16 with the same credentials

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=1                   # see ../.env.example for all settings
python manage.py migrate                # also creates the units, roles and default permissions
python manage.py createsuperuser        # your first Super Admin
python manage.py create_demo_users      # optional, dev only: one account per role
python manage.py runserver

cd ../frontend
npm install
npm run dev                             # http://localhost:5173 (proxies /api and /admin to :8000)
```

Run the backend tests with `DJANGO_DEBUG=1 python manage.py test accounts`.

## How access works

| Concept | Where it lives |
| --- | --- |
| Units | `Unit` model: Web App Development, Training, Academic Content Writing |
| Roles | `Role` model, each belonging to one unit, with a set of capabilities |
| Users | `User.role` (one role). `User.unit` is read from the role, so a user can't hold a role from another unit. A database constraint requires a role for everyone except Super Admins. |
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
| | Team Lead | + task assignment, team overview |
| Training | Student | courses, my progress |
| | Instructor | unit directory, courses, my classes, grading |
| | Front Desk Coordinator | unit directory, courses, enquiries, enrollments |
| | Training Manager | unit directory, courses, enquiries, enrollments, batches, training reports |
| Academic Content Writing | Content Writer | unit directory, my assignments |
| | Content Writer & Research Specialist | + research |
| | Production Manager | unit directory, quality review, production pipeline |
| | Sales Executive | unit directory, leads & orders |
| | Sales Manager | + sales reports, sales team |
| | HR | unit directory, employee records |

Only the unit directory is a working feature today; the other dashboard
cards are placeholders for the features each unit will need.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/auth/csrf/` | Sets the CSRF cookie |
| `POST /api/auth/login/` | Session login, returns the current user |
| `POST /api/auth/logout/` | Ends the session |
| `GET /api/auth/me/` | Current user, unit, role, capabilities, dashboard |
| `GET /api/unit/members/` | People in your unit (needs `view_unit_directory`) |
