# miniOrange IT Helpdesk Tool

Internal FastAPI + vanilla-JS Windows diagnostics and maintenance tool. Both
employees (self-service diagnostics) and IT technicians use the same app.
All 21 tools are currently open to every authenticated user — Device
Manager/Services/`cmd` rely on Windows UAC and your AD admin-group policy to
block non-admins from making real changes; `cmd` is not gated by UAC and was
opened anyway as an explicit decision (see `logs/audit.log`/`audit_log` for
who used it and when).

## Setup

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m backend.cli create-user --email you@company.local --display-name "Your Name" --role technician
```

`create-user` prompts for a password (min 8 chars) and creates a **local**
account — the right thing for a break-glass/admin account, or for
`LDAP_ENABLED=false` setups. `--role employee` for non-technician accounts.
`list-users` / `deactivate-user` are also available.

## Active Directory login (optional)

By default, auth is local (email + password stored here). To authenticate
against your AD instead — regular accounts get created automatically the
first time someone logs in, with no separate account to provision — set:

```
LDAP_ENABLED=true
LDAP_DOMAIN=ad.xecurify.com          # confirm this is your real AD domain
LDAP_TECHNICIAN_GROUP=IT-Technicians # AD group whose members get the technician role
LDAP_USE_SSL=true
```

**Confirm both values above before flipping `LDAP_ENABLED` on** — `LDAP_DOMAIN`
was inferred from this dev machine's own DNS suffix and may not be your real
domain; `LDAP_TECHNICIAN_GROUP` needs to be the actual AD group name you want
mapped to the technician role.

How it works: the app binds directly to AD as the logging-in user
(`username@your-domain`, no separate service account needed), which both
verifies their password and lets it read their own `memberOf` attribute for
role mapping. A local account with `auth_source=local` (any account made via
`create-user`) still works even when LDAP is enabled — that's the intended
break-glass path if AD is ever unreachable. Local accounts created via
`create-user` after LDAP is enabled are for that purpose only; everyone else
should just log in with their normal AD credentials.

## Config

Environment variables (all optional, sensible defaults apply) or a `.env`
file in the repo root:

| Variable | Purpose |
|---|---|
| `DATABASE_URL`, `LOG_DIR` | storage locations |
| `SESSION_COOKIE_NAME`, `SESSION_TTL_HOURS`, `SECURE_COOKIES` | session cookie behavior — set `SECURE_COOKIES=true` once served over HTTPS |
| `HOST`, `PORT` | what `run_prod.bat` binds to (default `127.0.0.1:8000`) |
| `SSL_KEYFILE`, `SSL_CERTFILE` | set both to have `run_prod.bat` terminate TLS directly |
| `LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_MINUTES` | login lockout policy (default 5 attempts / 15 min) |
| `LDAP_ENABLED`, `LDAP_DOMAIN`, `LDAP_TECHNICIAN_GROUP`, `LDAP_USE_SSL` | see above |
| `TICKETING_URL` | shown as "Raise a Ticket" in the nav and on generated reports |

## Running

**Local dev** (auto-reload on file changes):

```bat
run.bat
```

**Production** (no reload, single worker — see note below):

```bat
run_prod.bat
```

Both serve on `127.0.0.1:8000` by default. Sign in at `/login`.

### Deploying beyond localhost

This app currently assumes single-worker, per-machine deployment — the
power-action cooldown and login rate-limiter keep their state in memory, so
running multiple `uvicorn` workers would fragment that state across
processes (fine to revisit if load testing ever shows it's needed; see
`scripts/loadtest.py`).

To expose it on the LAN instead of loopback-only:
1. Get a TLS certificate — a self-signed one for internal testing
   (PowerShell: `New-SelfSignedCertificate -DnsName "yourhost" -CertStoreLocation cert:\LocalMachine\My`,
   then export to `.pfx`/`.pem`), or one from your internal CA for real use.
   Set `SSL_KEYFILE`/`SSL_CERTFILE` to the key/cert paths.
2. Set `SECURE_COOKIES=true` (cookies won't be sent over plain HTTP once this is on).
3. Set `HOST=0.0.0.0` (or a specific interface) and `PORT` as needed.
4. Run `run_prod.bat`.

A `GET /healthz` endpoint (no auth) is available for uptime monitoring.

## Backup / restore

```bat
python -m backend.cli backup-db
```

Writes a timestamped, safely-copied backup (uses SQLite's own backup API, so
it's consistent even against a live WAL-mode database) to `backups/`. To
restore: stop the app, copy the desired backup file over `data/helpdesk.db`,
restart. Consider a nightly Windows Scheduled Task running the command above.

## Tests

```bat
pytest -v
```

CI runs the same suite on every push/PR via `.github/workflows/tests.yml`.
`scripts/loadtest.py` is a manual sanity check (not part of the suite) for
concurrent-load behavior against a running instance.

## Notes

- Every tool invocation (launch/command/power) and every login/logout/lockout
  event is audited to the `audit_log` table and to `logs/audit.log` (JSON
  lines), including who, success/failure, and timing.
- SQLite database lives at `data/helpdesk.db`.
