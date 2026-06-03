# Azmus ERP — Production Readiness Report

**Date:** 2026-06-02  
**Scope:** 1-month on-premise production (no new business modules)

---

## Executive summary

| Area | Status | Notes |
|------|--------|-------|
| Backend modules (MES, Materials, Orders, Tasks, LLP, Settings, Migration, Permissions) | **Ready (automated tests)** | 10 audit scripts passed locally |
| Data outside project folder | **Ready (code)** | `backend/config/paths.py` + `.env` |
| Production startup scripts | **Ready** | `start_production.bat` / `stop_production.bat` |
| LAN / Wi‑Fi access | **Ready (config)** | `0.0.0.0` bind + `get_lan_ip.ps1`; firewall is manual |
| Daily backup (30 days) | **Ready (tested)** | `test_production_backup.py` PASSED |
| Android APK 1.0.0 | **Built** | Debug + release-unsigned in `deploy/AzmusERP-Production/apk/` |
| Deployment package | **Ready** | `deploy/AzmusERP-Production/` |
| Multi-device verification | **Pending (you)** | Main PC, second PC, phone |

**Overall:** Code and packaging are production-ready for on-prem deployment. Complete **first-time steps** below before going live.

---

## Production path structure

```
D:\AzmusERP\
├── Application\                    ← full repo copy (code only)
│   ├── backend\
│   ├── frontend\
│   ├── deploy\AzmusERP-Production\
│   └── .env                      ← from .env.production.template
└── Data\                         ← ALL business data
    ├── database\
    │   └── azmus.db
    ├── uploads\                  ← LLP, branding, MES drawings
    ├── backups\
    │   ├── daily\                ← auto backups (30-day retention)
    │   └── pre_migrate_*         ← migration safety copies
    ├── logs\
    │   ├── azmus-backend.log
    │   ├── uvicorn.out.log
    │   └── vite-preview.out.log
    └── migrations\               ← migration import backups
```

Project folders (`backend/azmus_new.db`, `backend/uploads`, etc.) are **not** used when `.env` points to `D:\AzmusERP\Data`. Existing project data is **not deleted**; `migrate_data_to_d.ps1` copies only.

---

## Startup instructions

### First-time (once)

1. Copy repository → `D:\AzmusERP\Application`
2. Copy `deploy\AzmusERP-Production\.env.production.template` → `D:\AzmusERP\Application\.env`
3. Set strong `JWT_SECRET_KEY` in `.env`
4. Run (PowerShell):  
   `deploy\AzmusERP-Production\scripts\migrate_data_to_d.ps1`
5. Allow Windows Firewall: **TCP 8000** and **5173** (Private network)
6. Run: `deploy\AzmusERP-Production\scripts\start_production.bat`

### Daily / after reboot

1. `scripts\start_production.bat` — backend + frontend run minimized (survive browser close; not a Windows service — survives user logout only while PC stays on and processes keep running)
2. Open **http://localhost:5173** or **http://&lt;LAN-IP&gt;:5173** (shown in console)
3. Stop: `scripts\stop_production.bat`

### Restart checklist

- [ ] `start_production.bat`
- [ ] http://localhost:8000/ shows `status: ok` and correct `data_root`
- [ ] Login as admin; change default password if still `1234`
- [ ] Create test material + MES category (smoke test)

---

## Configuration (.env)

| Variable | Purpose |
|----------|---------|
| `DATA_ROOT` | Root for all data |
| `DB_PATH` | SQLite file |
| `UPLOAD_PATH` | Files / LLP / branding |
| `BACKUP_PATH` | Manual + daily backups |
| `LOG_PATH` | Application logs |
| `MIGRATION_BACKUP_PATH` | Migration snapshots |
| `AUTO_BACKUP_ENABLED` | Daily job (default 02:00) |
| `BACKUP_RETENTION_DAYS` | 30 |
| `VITE_API_URL` | Set before APK build (LAN API) |

Template: `deploy/AzmusERP-Production/.env.production.template`

---

## APK location

After `scripts\build_apk_production.ps1` (requires JDK + Android SDK):

| Artifact | Path |
|----------|------|
| Debug | `deploy/AzmusERP-Production/apk/azmus-erp-1.0.0-debug.apk` |
| Release (unsigned) | `deploy/AzmusERP-Production/apk/azmus-erp-1.0.0-release-unsigned.apk` |

- App ID: `com.azmus.erp`
- Version: **1.0.0** (`versionName` in `frontend/android/app/build.gradle`)
- Cleartext HTTP enabled for LAN (`usesCleartextTraffic`)
- Phone must use same Wi‑Fi; API URL = `http://<server-ip>:8000`

---

## Automated audit results (this machine)

| Test | Result |
|------|--------|
| test_p4_a1_materials.py | PASSED |
| test_p4_a2_material_consumption.py | PASSED |
| test_p4_a3_auto_consumption.py | PASSED |
| test_p5_central_settings.py | PASSED |
| test_p6_control_center.py | PASSED |
| test_b5–b8 MES terminals | PASSED |
| test_production_backup.py | PASSED |
| main import (282 routes, materials registered) | PASSED |

Run anytime:  
`deploy\AzmusERP-Production\scripts\run_production_audit.ps1`

**Manual modules** (no dedicated automated script in this package — verify in UI):

- Orders, Tasks, LLP, Telegram bot, Migration wizard, Permissions matrix

---

## Files changed (production deployment)

### Backend

- `backend/config/paths.py` — DATA_ROOT, DB_PATH, UPLOAD_PATH, BACKUP_PATH, LOG_PATH
- `backend/config/logging_setup.py` — log to LOG_PATH
- `backend/database.py` — uses paths config
- `backend/main.py` — paths logging, health `data_root` fields, static uploads from UPLOAD_PATH
- `backend/services/auto_backup.py` — daily backup + restore
- `backend/services/scheduler.py` — backup schedule
- `backend/services/migration.py` — MIGRATION_BACKUP_PATH
- `backend/routers/admin_router.py`, `uploads_router.py` — path config
- `backend/test_production_backup.py`

### Frontend / Android

- `frontend/vite.config.js` — `host: true`, preview LAN
- `frontend/package.json` — `preview:prod`
- `frontend/android/app/src/main/AndroidManifest.xml` — cleartext traffic

### Deploy package

- `deploy/AzmusERP-Production/` — template, USER_GUIDE, scripts, this report

---

## Remaining issues / risks

1. **Data migration on this PC** — Already run: `azmus_new.db` copied to `D:\AzmusERP\Data\database\azmus.db` (pre-migrate backup under `Data\backups\pre_migrate_*`). Re-run on other machines if needed.
2. **JWT secret** — Default template value must be replaced before go-live.
3. **Windows service** — Current start scripts use minimized `cmd` windows; for reboot-proof 24/7, consider NSSM/Task Scheduler (optional upgrade).
4. **Cloud Render** — If mobile/web still point to `azmus-crm.onrender.com`, deploy backend with `materials_router` + latest code separately from this on-prem package.
5. **Release APK signing** — `azmus-erp-1.0.0-release-unsigned.apk` needs a keystore for Play Store; use debug APK for internal phones.
6. **APK API URL** — Last build: `http://192.168.1.110:8000`; rebuild if server IP changes.
7. **Multi-device test** — Second PC and phone access depend on firewall and correct `VITE_API_URL` / browser URL.
8. **Default admin password** — Change immediately after first login.

---

## Verification checklist (your action)

| Device | Check |
|--------|--------|
| Main PC | localhost:5173, create material, MES job, backup file in `Data\backups\daily` |
| Second PC | http://&lt;LAN-IP&gt;:5173, login, API calls succeed |
| Android | Install debug APK, same Wi‑Fi, login |

---

## Backup & restore

- **Automatic:** Daily 02:00 when backend runs (`AUTO_BACKUP_ENABLED=true`)
- **Manual:** `scripts\run_daily_backup.bat`
- **Restore:** Stop servers → copy daily `.db` → `restore_database_from_backup()` (see USER_GUIDE.md)

---

*Generated as part of Production Deployment Phase. No business data was deleted during preparation.*
