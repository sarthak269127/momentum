# Momentum

A personal productivity web application built with Flask. Track tasks, habits, focus sessions, notes, and upcoming event countdowns — all in one place.

---

## Features

| Module | Description |
|---|---|
| **Tasks** | To-do list with priorities, due dates, and overdue tracking |
| **Habits** | Daily/weekday/interval habit streaks with 30-day heatmaps |
| **Focus Timer** | Countdown timer + stopwatch with session persistence and weekly stats |
| **Notes** | Rich note editor with autosave and browser-notification reminders |
| **Calendar** | Monthly calendar view with per-day task breakdown |
| **Countdowns** | Live event countdowns (days / hours / minutes / seconds) |
| **Dashboard** | Overview of today's tasks, focus time, habit streaks, and upcoming events |

---

## Architecture

```
momentum/
├── app.py                  # Application factory (create_app)
├── auth.py                 # Authentication blueprint
├── config.py               # Dev / Production / Testing config classes
├── extensions.py           # Flask extension singletons (db, login_manager, mail)
├── models.py               # SQLAlchemy ORM models
├── csrf_utils.py           # Lightweight CSRF protection decorator
│
├── blueprints/             # Feature blueprints (one per module)
│   ├── dashboard.py
│   ├── tasks.py
│   ├── notes.py
│   ├── habits.py
│   ├── timer.py
│   ├── countdowns.py
│   └── calendar.py
│
├── services/               # Business logic extracted from blueprints
│   ├── email_service.py    # Password-reset email delivery
│   ├── focus_service.py    # Focus session queries and formatting
│   └── note_service.py     # Reminder-task synchronisation
│
├── static/
│   ├── css/                # Modular stylesheets (base, layout, components, …)
│   └── js/                 # Page-specific scripts + shared utils.js
│
├── templates/
│   ├── auth/               # Login, register, forgot/reset password
│   ├── main/               # App pages (dashboard, tasks, habits, …)
│   └── errors/             # 400, 403, 404, 500 error pages
│
├── tests/                  # pytest test suite
│   ├── conftest.py         # Shared fixtures
│   ├── test_auth.py
│   ├── test_tasks.py
│   ├── test_notes.py
│   ├── test_timer.py
│   ├── test_habits.py
│   └── test_services.py
│
├── .env                    # Local secrets (never commit)
├── .env.example            # Documentation template for .env
└── requirements.txt
```

### Key Design Decisions

- **Application factory pattern** — `create_app(config_name)` allows multiple instances (dev, test, prod) without circular imports.
- **Blueprint-per-feature** — each feature is an isolated, reusable module with its own URL prefix.
- **Service layer** — business logic that is shared across blueprints (focus stats, reminder-task sync) lives in `services/` and is independently testable.
- **CSRF without flask-wtf** — a lightweight session-token decorator works for both HTML form POSTs and JSON AJAX requests.
- **No magic numbers** — all constants (title lengths, password minimums, session caps) are defined in `config.py` and referenced as `current_app.config["CONSTANT"]`.

---

## Setup (Local Development)

### 1. Clone and enter the project

```bash
git clone <repo-url> momentum
cd momentum
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Random 64-char hex string — `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SECURITY_PASSWORD_SALT` | Second random string for password-reset tokens |
| `MAIL_USERNAME` | SMTP sender address |
| `MAIL_PASSWORD` | SMTP password |

### 5. Run

```bash
flask run
# or
python app.py
```

The app is available at `http://localhost:5000`.

---

## Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `SECRET_KEY` | *(none)* | **Yes** | Flask session signing key |
| `SECURITY_PASSWORD_SALT` | *(none)* | **Yes** | itsdangerous salt for reset tokens |
| `FLASK_ENV` | `development` | No | `development` / `production` / `testing` |
| `FLASK_DEBUG` | `1` | No | Enable debug mode |
| `DATABASE_URL` | `sqlite:///users.db` | No | SQLAlchemy database URI |
| `MAIL_SERVER` | `smtp.zoho.in` | No | SMTP server hostname |
| `MAIL_PORT` | `587` | No | SMTP port |
| `MAIL_USE_TLS` | `true` | No | Enable STARTTLS |
| `MAIL_USERNAME` | *(none)* | For email | SMTP sender address |
| `MAIL_PASSWORD` | *(none)* | For email | SMTP password |
| `SESSION_COOKIE_SECURE` | `false` | No | Set `true` in production (requires HTTPS) |

---

## Running Tests

```bash
# Run all tests
pytest

# With output
pytest -v

# Single test file
pytest tests/test_auth.py -v

# Coverage report (install pytest-cov first)
pip install pytest-cov
pytest --cov=. --cov-report=term-missing
```

Tests use an in-memory SQLite database and disable CSRF validation so no external services are required.

---

## Production Deployment

### Using Gunicorn

```bash
pip install gunicorn
gunicorn "app:create_app('production')" --bind 0.0.0.0:8000 --workers 4
```

### Environment checklist before deploying

- [ ] `SECRET_KEY` is a long, unique random string
- [ ] `SECURITY_PASSWORD_SALT` is a different long random string
- [ ] `FLASK_ENV=production`
- [ ] `FLASK_DEBUG=0`
- [ ] `SESSION_COOKIE_SECURE=true` (requires HTTPS)
- [ ] `DATABASE_URL` points to a production database (PostgreSQL recommended)
- [ ] `MAIL_USERNAME` and `MAIL_PASSWORD` are set
- [ ] `.env` is **not** committed to source control
- [ ] A reverse proxy (nginx/caddy) terminates TLS before Gunicorn

### Database migrations

The app calls `db.create_all()` on startup which creates any missing tables. For production schema changes use Flask-Migrate:

```bash
pip install flask-migrate
flask db init
flask db migrate -m "description"
flask db upgrade
```

---

## Security Notes

- All passwords are hashed with `werkzeug.security.generate_password_hash` (PBKDF2/SHA-256).
- Password-reset tokens are signed with `itsdangerous.URLSafeTimedSerializer` and expire after 10 minutes.
- The forgot-password endpoint always returns the same response whether or not the email exists (prevents user enumeration).
- After login, the `next` redirect parameter is validated to block open-redirect attacks.
- CSRF tokens protect all state-mutating routes (POST/PUT/DELETE/PATCH).
- All user-owned resources enforce ownership checks — a user cannot read, modify, or delete another user's data.
- SQL injection is prevented by SQLAlchemy's parameterised queries (no raw SQL).

---

## Logs

Application logs are written to `logs/momentum.log` with rotation at 5 MB (5 backups kept). In development the log level is DEBUG; in production it is INFO.
