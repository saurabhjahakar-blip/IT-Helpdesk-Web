# miniOrange IT Helpdesk Tool

Internal FastAPI + vanilla-JS Windows diagnostics and maintenance tool. Both
employees (safe self-service diagnostics) and IT technicians (full toolset,
including power actions and shell access) use the same app, gated by role.

## Setup

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m backend.cli create-user --email you@company.local --display-name "Your Name" --role technician
```

`create-user` prompts for a password (min 8 chars). Use `--role employee` for
non-technician accounts. `list-users` / `deactivate-user` are also available.

Config is read from environment variables (all optional, sensible defaults
apply) or a `.env` file in the repo root: `DATABASE_URL`, `SESSION_COOKIE_NAME`,
`SESSION_TTL_HOURS`, `SECURE_COOKIES`, `LOG_DIR`. Set `SECURE_COOKIES=true`
once the app is served over HTTPS.

## Running

```bat
run.bat
```

Serves on `http://127.0.0.1:8000` (loopback only). Sign in at `/login`.

## Tests

```bat
pytest -v
```

## Notes

- Every tool invocation (launch/command/power) is audited to the `audit_log`
  table and to `logs/audit.log` (JSON lines), including who ran it, success,
  exit code, and duration.
- `device_manager`, `services`, `cmd`, `restart`, and `shutdown` are
  technician-only; everything else is available to employees.
- SQLite database lives at `data/helpdesk.db` — back it up manually for now.
