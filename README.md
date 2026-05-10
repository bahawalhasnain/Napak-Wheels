# Napak Wheels V2

Flask-based car marketplace with messaging, offers, test-drive booking, saved
searches, favorites, in-app notifications, an admin moderation panel,
analytics, CSV exports, a Flask-Admin DB panel, and a JSON API.

## Tech Stack

- Python 3.12
- Flask (app factory) + Flask-Login + Flask-Migrate (Alembic) + Flask-WTF (CSRF)
- Flask-SQLAlchemy / SQLAlchemy 2.x (Microsoft SQL Server via `pyodbc`; SQLite for tests)
- Flask-Admin (DB power tools)
- Celery (eager mode by default; Redis when `CELERY_BROKER_URL` is set)
- Bootstrap 5 + Font Awesome 6 + Chart.js (analytics)
- pytest + pytest-flask

## Features

### Buyers and sellers
- Browse, filter, search car listings (paginated JSON API as well)
- Save / Favorite listings (`/my_favorites`)
- Saved searches with email + in-app alerts when a matching car is posted
- In-app messaging (no phone numbers shared by default)
- Make-an-offer flow with full counter-offer history
- Test-drive booking with date/time slots and seller confirm/decline
- Report a listing (spam, fraud, sold, etc.)

### Listings
- Multi-photo upload (max 6) with background image processing via Celery
- Tag-based features
- Owners can edit, mark as sold, or delete their listings
- Per-listing view counter with "X people viewed today" (deduped per user/session/day; owner and admin views excluded)

### Admin & analytics
- Curated dashboard at `/admin` with at-a-glance KPIs
- Reports moderation queue with take-down / restore actions
- User management with grant/revoke admin
- Listings overview filterable by status (active / taken-down)
- Analytics page at `/admin/analytics` (Chart.js):
  - New listings per day (last 30)
  - Page views per day (last 30)
  - Top makes
  - Sold conversion (donut: sold / active / taken down)
  - Most-viewed listings leaderboard
- CSV export endpoints (admin-only):
  - `/admin/export/cars.csv`
  - `/admin/export/users.csv`
  - `/admin/export/reports.csv`
- Flask-Admin DB power-tools panel at `/admin/db` for raw CRUD on every model
- CLI: `flask --app app make-admin user@example.com`

## Project layout

```
app.py                  # Application factory + CLI commands
main.py                 # Entry point (python main.py)
config.py               # Config + TestConfig
extensions.py           # db, migrate, login_manager, csrf
models.py               # All ORM models
forms.py                # All WTForms
routes.py               # Main blueprint (auth, listings, favorites)
api.py                  # /api/v1 JSON API
admin_panel.py          # Flask-Admin DB panel mounted at /admin/db
decorators.py           # @admin_required
email_utils.py          # SMTP sender (logs in dev)
tasks.py                # Celery app + tasks (images, alerts, email)
blueprints/
  messaging.py          # In-app chat
  offers.py             # Make/accept/reject/counter offers
  test_drives.py        # Test-drive bookings
  saved_searches.py     # Saved searches + alerts toggle
  reports.py            # Report a listing
  admin.py              # Admin dashboard, moderation, analytics, CSV export
  notifications.py      # In-app notifications
templates/              # Jinja templates per blueprint folder
static/                 # CSS + JS
tests/                  # pytest suite
```

## Prerequisites

- Python 3.12
- SQL Server running (or SQLite for local dev — set `DATABASE_URL=sqlite:///napak_wheels.db`)
- ODBC Driver 17 for SQL Server (Windows) if using SQL Server

## Setup

1. Create / activate a virtualenv:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in values.

4. Initialize the database with Flask-Migrate (first time only):

```bash
flask --app app db init
flask --app app db migrate -m "initial schema"
flask --app app db upgrade
```

For subsequent model changes, run:

```bash
flask --app app db migrate -m "describe change"
flask --app app db upgrade
```

5. (Optional) Promote a user to admin:

```bash
flask --app app make-admin you@example.com
```

## Run

```bash
python main.py
```

App starts on `http://127.0.0.1:5000`.

## Background workers

Without a broker, Celery runs tasks synchronously inside the request — perfect
for development. To run a real worker:

```bash
# 1. Start Redis (e.g. via Docker)
docker run --rm -p 6379:6379 redis:7

# 2. In .env, set:
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_TASK_ALWAYS_EAGER=0

# 3. Start a worker
celery -A tasks.celery worker --loglevel=info
```

## Email alerts

By default emails are logged to the console. To send real emails, configure SMTP
in `.env`:

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USERNAME=you@gmail.com
MAIL_PASSWORD=app-specific-password
MAIL_DEFAULT_SENDER=Napak Wheels <you@gmail.com>
```

## Tests

```bash
pytest -v
```

The suite uses an in-memory SQLite database, eager Celery, and SMTP-suppressed
mail — no external services required.

## JSON API

| Method | Path                            | Description                      |
| ------ | ------------------------------- | -------------------------------- |
| GET    | `/api/v1/cars`                  | Paginated, filterable car list   |
| GET    | `/api/v1/cars/<id>`             | Single car (with seller info)    |
| GET    | `/api/v1/favorites`             | Current user's favorites         |
| POST   | `/api/v1/favorites/<car_id>`    | Save a car                       |
| DELETE | `/api/v1/favorites/<car_id>`    | Unsave a car                     |

The API blueprint is CSRF-exempt; auth uses the same session cookie as the web
app, and unauthenticated requests get JSON `401`.

## Security notes

- Do not commit `.env` or `login_credential.txt`
- Set `SESSION_COOKIE_SECURE=1` when serving over HTTPS
- Rotate `SECRET_KEY` and DB password before production
- Use `flask db upgrade` rather than ad-hoc `ALTER TABLE` in production
- Run behind a real WSGI server (`waitress`, `gunicorn`); `python main.py` is
  for development only
