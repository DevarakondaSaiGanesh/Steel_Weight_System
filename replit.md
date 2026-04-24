# Steel Weight Calculation System

A web application for engineering teams to track steel material weights across projects.

## Stack
- **Backend:** FastAPI (Python 3.11) — JSON-only API
- **Frontend:** Plain static `.html` files + Bootstrap 5 (CDN) + vanilla JS (fetch) + Chart.js
- **Database:** PostgreSQL (SQLAlchemy)
- **Auth:** Local username/password (bcrypt) + signed cookie sessions

## Roles
- `admin` — full access; creates users/projects, assigns users, sees admin dashboard
- `user` — submits calculations to assigned projects
- `viewer` — read-only access to assigned projects

## Default credentials
Seeded on first run: `admin` / `admin123` (forced password change on first login).

## Layout
```
app/
  main.py              FastAPI JSON API + static mount
  models.py            SQLAlchemy models
  database.py          Engine + session factory
  auth.py              Hashing, password gen, role guards, weight formula
  web/                 Static HTML files (served at /)
    login.html
    change-password.html
    admin.html
    users.html
    admin-projects.html
    assign.html
    projects.html
    workspace.html
    project-dashboard.html
    css/app.css
    js/api.js          fetch wrapper, helpers
    js/nav.js          shared nav bar bootstrapping
```

## API summary
All endpoints are JSON under `/api/*`:
- Auth: `POST /api/login`, `POST /api/logout`, `GET /api/me`, `POST /api/change-password`
- Meta: `GET /api/meta` (materials, density)
- Admin users: `GET/POST/PATCH/DELETE /api/admin/users[/{id}[/role|reset-password]]`
- Admin projects: `GET/POST/PATCH/DELETE /api/admin/projects[/{id}]`, assignments under `/assignments`
- Admin dashboard: `GET /api/admin/dashboard`
- User: `GET /api/projects`, `GET /api/projects/{id}`, `POST/DELETE` calculations, `GET /api/projects/{id}/dashboard`

## Weight formula (density 7850 kg/m³)
- Round materials (Rod, MS Pipe): `(π · D² / 4 · L · 7850 · qty) / 1e9`
- All others: `(L · W · T · 7850 · qty) / 1e9`  (mm → kg)

## Run
Workflow `Start application`: `uvicorn app.main:app --host 0.0.0.0 --port 5000`

## Environment
- `DATABASE_URL` — PostgreSQL connection
- `SESSION_SECRET` — cookie signing secret
