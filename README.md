# Yeticode Innovations internal app

Role-based access for Yeticode's three units. There is no public sign-up:
a Super Admin creates every account in the Django admin and gives it one role,
and the role decides the person's unit, permissions and dashboard.

- `backend/` — Django 5.2 LTS, Django REST Framework, PostgreSQL
- `frontend/` — React 19 + Vite

## Running it locally

### 1. Database

The backend expects a PostgreSQL role and database both named `yeticode`
(password `yeticode`). Pick one option.

**Homebrew PostgreSQL on macOS** (`brew install postgresql@16 && brew services start postgresql@16`):

```bash
psql postgres -c "CREATE ROLE yeticode WITH LOGIN PASSWORD 'yeticode' CREATEDB;"
createdb -O yeticode yeticode
```

**Docker**: `docker compose up -d db` creates both for you. Stop any other
PostgreSQL on port 5432 first, or the two will clash.

### 2. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # local settings, loaded automatically; git ignores .env
python manage.py migrate                # also creates the units, roles and default permissions
python manage.py createsuperuser        # your first Super Admin
python manage.py create_demo_users      # optional, dev only: one account per role
python manage.py runserver              # http://localhost:8000/admin/
```

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
| | Team Lead | + task assignment, team overview |
| Training | Student | unit directory, courses, my progress |
| | Instructor | unit directory, courses, my classes, grading |
| | Front Desk Coordinator | unit directory, courses, enquiries, enrollments |
| | Training Manager | unit directory, courses, enquiries, enrollments, batches, training reports |
| Academic Content Writing | Content Writer | unit directory, my assignments |
| | Content Writer & Research Specialist | + research |
| | Production Manager | unit directory, quality review, production pipeline |
| | Sales Executive | unit directory, leads & orders |
| | Sales Manager | + sales reports, sales team |
| | HR | unit directory, employee records (Academic Content Writing only) |
| All units | Head HR | employee records, company-wide employee records (everyone in all three units). No admin panel and cannot create accounts. |
| All units | Super Admin | everything, plus the admin panel: create accounts, manage units, roles and permissions |

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
