# Velcore ERP — Production Deployment Report

**Date:** 2026-06-16  
**Target:** Ubuntu 24.04 VPS (`89.39.95.189`)  
**Domains:** `https://erp.velcore.uz` (frontend), `https://api.velcore.uz` (API)  
**App path:** `/var/www/velcore`  
**Environment:** `/etc/velcore/.env`

---

## Executive summary

Production failures were caused by a combination of **SQLite-only startup guards running against PostgreSQL**, **JWT/env loading order**, **frontend built with `127.0.0.1` API URL**, **no persistent systemd service**, and **lifespan `SystemExit(1)`** killing uvicorn during guard failures. All issues have been fixed in code; apply on VPS with `git pull` and `bash deploy/enterprise/scripts/vps_production_fix.sh`.

---

## Errors found

| # | Component | Error | Impact |
|---|-----------|-------|--------|
| 1 | `database_guard.py` | `ENVIRONMENT=production` enabled SQLite file guard on PostgreSQL | Lifespan crash: “Production database not found at …/azmus.db” |
| 2 | `database_guard.py` | `SKIP_DEMO_SEED=true` also enabled SQLite guard | Same crash on VPS even with empty SQLite path |
| 3 | `main.py` lifespan | `raise SystemExit(1)` on guard failure | systemd saw immediate exit; crash loop without clear uvicorn error |
| 4 | `paths.py` | Early-return env load; `backend/.env` could block `/etc/velcore/.env` | `JWT_SECRET_KEY` missing at runtime → login 503 |
| 5 | `paths.py` | Default `DATA_ROOT=D:\AzmusERP\Data` on Linux | Wrong log/upload paths when env missing |
| 6 | `frontend/.env.production` | `VITE_API_URL=http://127.0.0.1:8000` | Browser calls localhost → login stuck on “Yuklanmoqda…” |
| 7 | `remote-api.json` | Could override production API URL | Login/API calls to wrong host |
| 8 | Deployment | Manual `nohup uvicorn` only | Process dies on SSH disconnect / reboot |
| 9 | `velcore.service` | No `ExecStartPre` for log dirs | `StandardOutput=append:` could fail if logs dir missing |
| 10 | `scheduler.py` | Daily SQLite backup scheduled on PostgreSQL | Logged exceptions every night (non-fatal) |
| 11 | `main.py` | `/docs` disabled in production without override | User expected `api.velcore.uz/docs` |
| 12 | CORS | Only explicit env value used | Missing `https://erp.velcore.uz` if env misconfigured |

---

## Fixes applied

| # | File | Fix |
|---|------|-----|
| 1–2 | `backend/config/database_guard.py` | SQLite guard **disabled for PostgreSQL** unless `DATABASE_GUARD=true`; added `verify_database_connectivity()` for all server DBs |
| 3 | `backend/main.py` | Re-raise `DatabaseGuardError` / `RuntimeError` instead of `SystemExit(1)`; wrap seed in try/except; validate JWT + `DATABASE_URL` at startup |
| 4–5 | `backend/config/paths.py` | Load **all** env files (lowest priority first); Linux default `DATA_ROOT=/var/lib/velcore/data` |
| 4b | `backend/config/env_loader.py` | **Single env loader**; `/etc/velcore/.env` overrides `backend/.env` on Linux (`override=True`) |
| 6 | `frontend/.env.production.example` | `VITE_API_URL=https://api.velcore.uz` |
| 7 | `frontend/src/api/client.js` | (prior commit) Production builds ignore `remote-api.json`; `login()` awaits `ensureApiBase()` |
| 8–9 | `deploy/enterprise/systemd/velcore.service` | `Restart=always`, `EnvironmentFile`, `ExecStartPre` mkdir, `StartLimitBurst`, `PYTHONUNBUFFERED` |
| 10 | `backend/services/scheduler.py` | Skip daily SQLite backup when `DATABASE_URL` is not SQLite |
| 11 | `backend/main.py` + `env.production.example` | `ENABLE_API_DOCS=true` exposes `/docs` in production |
| 12 | `backend/config/production.py` | `parse_cors_origins()` always includes `https://erp.velcore.uz` |
| 13 | `backend/database.py` | PostgreSQL connection pool (`pool_size`, `max_overflow`, `pool_pre_ping`) |
| 14 | `deploy/enterprise/scripts/vps_production_fix.sh` | Full apply: env checks, DB ping, admin seed, systemd, frontend rebuild, nginx |

---

## Verified endpoints

### `GET /auth/login-users` (public)

- Router: `backend/routers/auth_router.py` → `@router.get("/login-users")`
- Returns active usernames for login dropdown
- No JWT required

### `POST /auth/login`

- Router: `backend/routers/auth_router.py` → `@router.post("/login")`
- Legacy alias: `POST /login` in `main.py`
- Requires `JWT_SECRET_KEY` from `/etc/velcore/.env` (lazy load via `get_secret_key()`)
- Returns 503 if JWT missing; 401 on bad credentials
- Default admin: `admin` / `1234` (via `ensure_admin_user.py` + `seed_defaults`)

### `GET /` health

- Reports `auth_configured`, database info, registered modules

---

## JWT_SECRET_KEY loading

Load order (systemd/process env wins):

1. Process environment (`EnvironmentFile=/etc/velcore/.env` in systemd)
2. `/etc/velcore/.env` (via `paths._load_env_files()`)
3. `backend/.env`, repo `.env` (fill gaps only, `override=False`)
4. `AZMUS_ENV_FILE` if set (override)

Auth reads secret at **call time** in `auth/security.py` → `get_secret_key()`.

---

## CORS configuration

Set in `/etc/velcore/.env`:

```env
CORS_ORIGINS=https://erp.velcore.uz
```

Notes:

- Browser requests from `https://erp.velcore.uz` → `https://api.velcore.uz` require this origin.
- `https://api.velcore.uz` is same-origin for API docs; CORS not needed for docs.
- Code auto-appends `https://erp.velcore.uz` if missing from env.

---

## Database initialization (lifespan)

1. `validate_runtime_config()` — JWT + `DATABASE_URL` required
2. `verify_database_connectivity()` — PostgreSQL `SELECT 1`
3. SQLite guard skipped for PostgreSQL
4. `Base.metadata.create_all()` — create tables
5. `run_migrations()` — SQLite ALTER only (no-op on PostgreSQL)
6. `seed_defaults()` — admin user, defaults (errors logged, non-fatal)
7. `start_reminder_scheduler()` — reminders + GPS alerts (SQLite backup skipped on PG)

---

## systemd service

Install:

```bash
sudo cp /var/www/velcore/deploy/enterprise/systemd/velcore.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now velcore.service
sudo systemctl status velcore.service
```

Logs:

```bash
tail -f /var/lib/velcore/data/logs/uvicorn.err.log
journalctl -u velcore.service -f
```

---

## VPS apply (one command)

```bash
cd /var/www/velcore
sudo bash deploy/enterprise/scripts/vps_production_fix.sh
```

Prerequisites:

- PostgreSQL running with database `azmus_erp`, user `azmus`
- `/etc/velcore/.env` with real `DATABASE_URL` password and `JWT_SECRET_KEY`
- Python venv at `/var/www/velcore/backend/.venv`
- Nginx configs for `erp.velcore.uz` and `api.velcore.uz`

---

## Post-deploy verification checklist

```bash
# Service running
systemctl is-active velcore.service

# Health
curl -s http://127.0.0.1:8000/ | jq .

# Public login users
curl -s http://127.0.0.1:8000/auth/login-users

# Login
curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"1234"}'

# HTTPS
curl -s https://api.velcore.uz/
curl -s https://api.velcore.uz/auth/login-users

# Frontend uses production API (browser devtools → Network → api.velcore.uz)
open https://erp.velcore.uz
```

---

## Files changed in this audit

```
backend/config/database_guard.py
backend/config/paths.py
backend/config/production.py          (new)
backend/main.py
backend/database.py
backend/services/scheduler.py
deploy/enterprise/systemd/velcore.service
deploy/enterprise/env.production.example
deploy/enterprise/scripts/vps_production_fix.sh
deploy/enterprise/PRODUCTION_DEPLOYMENT_REPORT.md  (this file)
frontend/.env.production.example      (new)
```

---

## Remaining operational notes

1. Change default admin password after first login.
2. Use `pg_dump` for PostgreSQL backups (SQLite auto-backup is intentionally disabled).
3. Rebuild frontend after any API URL change: `VITE_API_URL=https://api.velcore.uz npm run build`.
4. Do not commit `/etc/velcore/.env` or `frontend/.env.production` with secrets.
