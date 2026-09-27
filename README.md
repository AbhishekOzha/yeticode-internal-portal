# Yeticode Innovations internal app

Role-based access for Yeticode's three units. There is no public sign-up:
administrators create every account from the app's **Users** page and give it
one role, and the role decides the person's unit, permissions and dashboard.
Super Admins manage every unit; each unit's senior role (Team Lead, Training
Manager, Production Manager) manages accounts in its own unit only. The Django
admin panel is still there for Super Admins as a fallback.

- `backend/` — Django 5.2 LTS, Django REST Framework, PostgreSQL
- `frontend/` — React 19 + Vite + Ant Design 6 (light and dark themes)

## Running it locally

### 1. Database

Any PostgreSQL 16 works. The connection comes from `backend/.env` (step 2):
`DJANGO_DATABASE` (database name), `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
With Homebrew on macOS (`brew install postgresql@16 && brew services start postgresql@16`)
you can use your existing `postgres` user and its password.

With Docker instead, `docker compose up -d db` starts one with database, user and
password all set to `yeticode`; put those values in `.env`. Stop any other
PostgreSQL on port 5432 first, or the two will clash.

> **Upgrading a database from before UUIDs (September 2026)?** The migrations were reset for UUID ids, so an
> older database can't be migrated in place. Point `DJANGO_DATABASE` at a new, empty database and run
> `migrate` (then `create_default_users`); copy any data you need across.

### 2. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # then set DB_PASSWORD etc.; loaded automatically, git ignores it
python manage.py migrate                # also creates the units, roles and default permissions
python manage.py create_default_users  # Super Admin + one admin per unit (safe to re-run)
python manage.py create_demo_users      # optional, dev only: one sample person per role
python manage.py runserver              # http://localhost:8000/admin/
```

`create_default_users` makes these accounts if they don't exist yet. Everyone
signs in with their email (the domain comes from `DEFAULT_EMAIL_DOMAIN`):

| Sign-in email | Name | Role |
| --- | --- | --- |
| `admin@yeticode.com` (or `SYSTEM_USERNAME`) | System Administrator | Super Admin, all units |
| `webdev.lead@yeticode.com` | Web Development Lead | Team Lead, manages Web App Development users |
| `training.manager@yeticode.com` | Training Manager | Training Manager, manages Training users |
| `production.manager@yeticode.com` | Production Manager | Production Manager, manages Academic Content Writing users |

Accounts created by earlier versions (`superadmin`, `web_admin`, `training_admin`,
`content_admin`) are renamed to these emails in place, keeping their passwords.
Passwords come from `SYSTEM_USER_PASSWORD` and `UNIT_ADMIN_PASSWORD` in `.env`.
With `DEBUG=TRUE` and no password set, they default to `yeticode@123`; in
production the command refuses to run without them.

### 3. Frontend

```bash
cd frontend
yarn install                            # the project uses Yarn 1 (yarn.lock); `npm i -g yarn` if you don't have it
yarn dev                                # http://localhost:5173 (proxies /api, /admin and /media to :8000)
```

### Uploads

Profile photos and the company logo are stored under `backend/media/` (set
`MEDIA_ROOT` to change it; git ignores the folder). Images must be PNG, JPG or
WebP and at most 2 MB; SVG is refused because it can carry scripts. Django
serves `/media/` only while `DEBUG` is on, so in production serve `MEDIA_ROOT`
from your web server.

Check the frontend with `yarn lint` and `yarn build`. Run the backend tests with `python manage.py test` (needs the `CREATEDB` permission above).

## How access works

| Concept | Where it lives |
| --- | --- |
| IDs | Every record of the app's own (units, roles, users, company settings, payroll, office hours, chat, groups, reviews) has a random **UUID** primary key, so ids in URLs and the API can't be guessed or counted. Chat messages also carry an increasing `seq` from a database sequence, used for ordering, "new since", unread, delivered and seen. Django's built-in tables (permissions, content types, sessions) keep their own ids. |
| Units | `Unit` model: Web App Development, Training, Academic Content Writing |
| Roles | `Role` model with a set of capabilities. A role belongs to one unit, or to no unit when it is company-wide (Head HR). |
| Users | `User.role` (one role). `User.unit` is read from the role, so a user can't hold a role from another unit. A database constraint requires a role for everyone except Super Admins. |
| Unit isolation | Unit-scoped roles only ever see their own unit. Cross-unit capabilities (`CROSS_UNIT_CAPABILITIES` in `accounts/rbac.py`) can only be given to company-wide roles; the admin form, the model layer and the API each refuse otherwise. |
| Super Admin | `is_superuser`. The only users allowed into `/admin/`; they have every permission and no role. |
| Capabilities | Django permissions `accounts.<codename>`, defined in `accounts/rbac.py` and checked with `user.has_perm(...)`, or `has_capability(...)` in DRF views. |
| Dashboards | `/api/auth/me/` returns one dashboard widget per capability; the React app renders them. |
| Profiles | Everyone has a **My profile** page (user menu): they can upload their own photo and add, change or remove one secondary email. The primary email is the sign-in address; only Super Admins, or unit admins for other people in their unit, can change it, and it can never be blank. When a username was the email, it follows the new email. |
| Payroll | Academic Content Writing only (`payroll` app). Super Admins, and content-unit roles with `manage_payroll` (Production Manager and HR), set each person's monthly salary and default rates, and record extras per month: words (6,000 words = NPR 1,000 by default, so 3,000 words = NPR 500), hours (8 hours = NPR 1,000), performance and effort. Every amount is optional and the server does the calculation. A **daily log** per person holds each day's extra hours and words (one row per day; empty days had no extra work), and each day is priced on its own, e.g. 2 hours = NPR 250 one day and 12 hours = NPR 1,500 another. Only a Super Admin can change their own pay. |
| Office hours | Academic Content Writing only (`team` app). Super Admins, and the unit's Production Manager and HR, set each person's shift (presets 7–3, 9–5, 10–6, or custom); nobody but a Super Admin sets their own, work days (Sun–Fri by default) and whether they get reminders. While the app is open, people are reminded 30, 15 and 5 minutes before their shift starts and 5 minutes before log-out time, in the app and as a desktop notification if they allow it. Times use `DJANGO_TIME_ZONE`. |
| Team chat | Academic Content Writing only. Every active person in the unit sees the whole team, can post in the team room, message anyone in it one to one, and create **group chats** with chosen teammates (the group's creator or the Production Manager can rename it and add or remove people; anyone can leave). Messages show **✓ sent, ✓✓ delivered, blue ✓✓ seen** (in groups: "Seen by 2 of 5"), and people show a green dot when **online** or "Last seen …" otherwise; both come from the app's polling, so they can lag a few seconds, and "online" means the app is open in a tab (up to ~75 s to turn off). Nobody outside the unit can read or send, including Super Admins, and messages are not in the Django admin. The app polls for new messages every few seconds, shows unread badges and profile photos, and notifies about new messages. **Voice messages** (up to 5 minutes / 5 MB, recorded in the browser) are stored in `PRIVATE_MEDIA_ROOT` (`backend/private_media/`, git-ignored), never served as public media, and only played through the API to the people in that conversation. Recording needs a secure page: `http://localhost` or HTTPS. **Files** (Word, Excel, PowerPoint, PDF, CSV, text, OpenDocument, images, ZIP/RAR/7z; up to 20 MB) can be shared the same way. The type is checked by extension *and* by the file's contents, anything a browser could run (HTML, SVG, scripts, programs) is refused, files are stored under random names in `PRIVATE_MEDIA_ROOT`, and they download only for the people in that conversation (images preview inline). |
| Reviews | Academic Content Writing only. Everyone in the unit (writers, supervisors, the Production Manager, Sales Manager, HR, …) can rate any colleague 1–5 with an optional comment, once per person per month, and edit or withdraw it. Super Admins, HR and the Production Manager read them with the author's name; the person reviewed doesn't see them, and nobody reads the reviews about themselves. |
| Leave | Academic Content Writing only. Anyone in the unit applies for leave (type, dates, half day, reason) on the **Leave** page; the form names who will be told. The unit's Production Manager and HR are notified at once and approve or reject with an optional note (Super Admins can too); the applicant is notified of the decision. Nobody decides their own leave, and overlapping requests are refused. |
| Notifications | The bell in the header, for everyone. Other features call `notify()` (`notifications` app); the app checks every 15 seconds, pops up new ones (and a desktop notification when allowed) and opens the linked page on click. |
| Company branding | `CompanySettings` (a single row): name, tagline, contact details and logo. Only Super Admins edit it, on the **Company settings** page. The logo replaces the built-in mark in the sidebar, on the sign-in page and as the tab icon. |

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
| | Supervisor | unit directory, quality review |
| | Production Manager | unit directory, quality review, production pipeline, **staff payroll**, **user management (own unit)** |
| | Sales Executive | unit directory, leads & orders |
| | Sales Manager | + sales reports, sales team |
| | HR | unit directory, employee records, **staff payroll** (Academic Content Writing only) |
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
| `GET/PATCH /api/profile/` | Your own `avatar` (multipart upload, or `null` to remove) and `secondary_email`. The primary email is refused here. |
| `GET /api/payroll/staff/?month=YYYY-MM`, `PATCH /api/payroll/staff/<id>/` | Content staff with salary, rates and the month's totals; set someone's pay setup |
| `GET/PUT /api/payroll/staff/<id>/daily/?month=YYYY-MM` | A person's daily log: `{"days": [{"date", "hours", "words"}]}`. PUT replaces the month's dated hours/words extras; days left out had none. Unchanged days keep the rate they were priced at. |
| `GET/POST /api/payroll/extras/?month=YYYY-MM[&staff=<id>]`, `PATCH/DELETE /api/payroll/extras/<id>/` | A month's extras. Words and hours extras are priced from the rate; performance and effort take an amount. |
| `GET /api/team/office-hours/`, `PUT/DELETE /api/team/office-hours/<id>/` | Content staff shifts (Super Admin, Production Manager, HR) |
| `GET /api/team/office-hours/me/` | Your own shift and the office time zone, for reminders |
| `GET /api/team/reviews/people/?month=`, `POST /api/team/reviews/`, `DELETE /api/team/reviews/<id>/` | Your colleagues with your review of each; write/rewrite or withdraw your review |
| `GET /api/team/reviews/summary/?month=` | Everyone's reviews and average rating (Super Admin, HR, Production Manager; never your own) |
| `GET /api/chat/contacts/` | Your team, with each conversation's last message and unread count |
| `GET/POST /api/chat/messages/?with=team\|<id>\|g<id>[&after=<id>]` | Read messages (with receipts) or send one. Sending must name the conversation in `to`: `"team"`, a colleague's id, or `"g<id>"` for a group. |
| `GET /api/chat/messages/<id>/audio/` | Play a voice message (only for people in that conversation). Send one by POSTing `audio` (multipart) and `duration` to `/api/chat/messages/`. |
| `GET /api/chat/messages/<id>/file/` | Download a shared file (images open inline; `?download=1` forces a download). Send one by POSTing `file` (multipart) with an optional `body` caption. |
| `POST /api/chat/groups/`, `PATCH /api/chat/groups/<id>/`, `POST /api/chat/groups/<id>/leave/` | Create a group (`name`, `members`); rename it or `add`/`remove` members (creator or Production Manager); leave it |
| `POST /api/chat/read/`, `GET /api/chat/updates/?after=<id>` | Mark a conversation read; poll for unread counts and new messages |
| `GET/POST /api/team/leave/`, `POST /api/team/leave/<id>/cancel/` | Your leave requests and who will be notified; apply; cancel a pending request |
| `GET /api/team/leave/requests/?status=pending\|all`, `POST /api/team/leave/<id>/decide/` | The team's requests (Production Manager, HR, Super Admin); `{"decision": "approve"\|"reject", "note"}` |
| `GET /api/notifications/`, `POST /api/notifications/read/` | Your latest notifications and unread count; mark some (`ids`) or all read |
| `GET /api/branding/` | Company name, tagline and logo. Public, for the sign-in page. |
| `GET/PATCH /api/manage/company/` | Company details and `logo` (Super Admins only) |
| `GET /api/unit/members/` | People in your unit (needs `view_unit_directory`) |
| `GET /api/company/members/` | Everyone in every unit (company-wide roles with `view_all_employee_records`) |
| `GET/POST /api/manage/users/`, `GET/PATCH /api/manage/users/<id>/` | List, create, edit (including primary and secondary email), deactivate and reset passwords. Super Admins: all users. `manage_unit_users`: own unit, own unit's roles only. No DELETE; deactivate instead. |
| `GET /api/manage/roles/`, `PATCH /api/manage/roles/<id>/` | List roles (unit admins see their unit's); Super Admins edit a role's `capabilities` |
| `GET /api/manage/capabilities/` | The capability catalog (Super Admins) |
