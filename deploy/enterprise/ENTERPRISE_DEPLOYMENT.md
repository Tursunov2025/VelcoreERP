# Velcore ERP — Enterprise VPS Deployment Plan

**Target:** 24/7 production on Ubuntu 24.04 with PostgreSQL, Nginx, SSL  
**Domains:** `erp.azmus.uz` (UI) · `api.azmus.uz` (API)  
**Source data:** `D:\AzmusERP\Data\database\azmus.db` + `D:\AzmusERP\Data\uploads`

---

## 1. Server specification

### Recommended VPS (production)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| OS | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |
| vCPU | 2 | **4** |
| RAM | 4 GB | **8 GB** |
| Disk | 40 GB SSD | **80–120 GB SSD** |
| Bandwidth | 2 TB/mo | 3+ TB/mo |
| IPv4 | 1 static | 1 static |

**Why:** FastAPI + PostgreSQL + file uploads (MES drawings, LLP docs, APKs). Current SQLite DB ~1.2 MB; uploads grow over time. GPS + Telegram jobs need headroom.

### Suggested providers

| Provider | Plan example | Region | ~Monthly |
|----------|--------------|--------|----------|
| Hetzner | CPX31 (4 vCPU, 8 GB) | EU (Falkenstein/Helsinki) | €13–15 |
| DigitalOcean | Premium 4 GB / 8 GB | Frankfurt | $24–48 |
| AWS Lightsail | 4 GB | eu-central-1 | ~$24 |
| Local UZ host | 4 vCPU / 8 GB | Tashkent | $20–40 (varies) |

**DNS:** Point `erp.azmus.uz` and `api.azmus.uz` A records to VPS IP (at registrar for `.uz` domain).

### Server layout

```text
/var/www/azmus/
├── app/                    # git clone (AzmusCRM)
├── frontend/dist/          # built React SPA
└── releases/               # optional versioned deploys

/var/lib/azmus/data/
├── uploads/                # migrated from D:\AzmusERP\Data\uploads
├── backups/
│   ├── daily/              # pg_dump + uploads tar
│   └── logs/
├── logs/                   # uvicorn / nginx logs
└── migrations/             # pre-cutover SQLite snapshots

/etc/azmus/
├── .env                    # production secrets (chmod 600)
└── remote-api.json         # optional runtime API hint

PostgreSQL: database azmus_erp, user azmus_app
```

---

## 2. Architecture

```mermaid
flowchart TB
    subgraph Internet
        Phone[Phones / Browsers]
        Driver[Azmus Driver APK]
    end

    subgraph VPS["Ubuntu 24.04 VPS"]
        Nginx[Nginx + Let's Encrypt]
        UI[Static SPA erp.azmus.uz]
        API[FastAPI uvicorn api.azmus.uz]
        PG[(PostgreSQL azmus_erp)]
        Uploads[/var/lib/azmus/data/uploads]
        Cron[systemd timer: backup + healthcheck]
    end

    Phone --> Nginx
    Driver --> Nginx
    Nginx --> UI
    Nginx --> API
    API --> PG
    API --> Uploads
    Cron --> PG
    Cron --> Uploads
    Cron --> Telegram[Telegram alerts]
```

| Hostname | Serves |
|----------|--------|
| `https://erp.azmus.uz` | React `dist/` (SPA) |
| `https://api.azmus.uz` | FastAPI (uvicorn :8000) |
| `https://api.azmus.uz/uploads/` | Static files (or proxied from disk) |

---

## 3. Deployment steps

### Phase A — Server bootstrap (Day 1)

```bash
# As root on fresh Ubuntu 24.04
apt update && apt upgrade -y
apt install -y git curl ufw fail2ban nginx certbot python3-certbot-nginx \
  postgresql postgresql-contrib python3.12-venv python3-pip \
  pgloader rsync unzip

# Firewall
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable

# PostgreSQL
sudo -u postgres createuser azmus_app -P          # strong password
sudo -u postgres createdb azmus_erp -O azmus_app

# App user
useradd -r -m -d /var/www/azmus -s /bin/bash azmus
mkdir -p /var/lib/azmus/data/{uploads,backups/daily,logs,migrations}
chown -R azmus:azmus /var/www/azmus /var/lib/azmus
```

### Phase B — Application deploy

```bash
sudo -u azmus git clone https://github.com/YOUR_ORG/AzmusCRM.git /var/www/azmus/app
cd /var/www/azmus/app/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install psycopg2-binary   # add to requirements.txt for production

# Copy env template
cp /var/www/azmus/app/deploy/enterprise/env.production.example /etc/azmus/.env
chmod 600 /etc/azmus/.env
nano /etc/azmus/.env   # set JWT, DATABASE_URL, paths, Telegram
```

**`/etc/azmus/.env` essentials:**

```env
ENVIRONMENT=production
DATA_ROOT=/var/lib/azmus/data
UPLOAD_PATH=/var/lib/azmus/data/uploads
BACKUP_PATH=/var/lib/azmus/data/backups
LOG_PATH=/var/lib/azmus/data/logs
DATABASE_URL=postgresql+psycopg2://azmus_app:PASSWORD@127.0.0.1:5432/azmus_erp
JWT_SECRET_KEY=<64-char random>
CORS_ORIGINS=https://erp.azmus.uz
DATABASE_GUARD=false
SKIP_DEMO_SEED=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
APP_URL=https://erp.azmus.uz
AUTO_BACKUP_ENABLED=true
BACKUP_HOUR=2
BACKUP_MINUTE=0
REMINDER_TIMEZONE=Asia/Tashkent
```

### Phase C — SQLite → PostgreSQL migration

> **Prerequisite:** Add Postgres migration path in backend (Phase Enterprise code) OR use **pgloader** for one-time import.

**Option 1 — pgloader (fastest for cutover):**

```bash
# On Windows: copy azmus.db to VPS
scp D:/AzmusERP/Data/database/azmus.db azmus@VPS:/var/lib/azmus/data/migrations/

# On VPS — create pgloader.load:
cat > /tmp/pgloader.load <<'EOF'
LOAD DATABASE
  FROM sqlite:///var/lib/azmus/data/migrations/azmus.db
  INTO postgresql://azmus_app:PASSWORD@127.0.0.1/azmus_erp
  WITH include drop, create tables, create indexes, reset sequences
  SET work_mem to '16MB', maintenance_work_mem to '512 MB';
EOF

pgloader /tmp/pgloader.load
```

**Option 2 — Staged (lower risk):**

1. Deploy API on VPS still pointing at copied SQLite file (interim).
2. Validate ERP on `api.azmus.uz`.
3. Run pgloader during maintenance window.
4. Switch `DATABASE_URL` to PostgreSQL, restart API.

**Uploads migration:**

```bash
# From Windows (PowerShell)
scp -r D:\AzmusERP\Data\uploads\* azmus@VPS:/var/lib/azmus/data/uploads/
# Or rsync over SSH:
rsync -avz /mnt/d/AzmusERP/Data/uploads/ azmus@VPS:/var/lib/azmus/data/uploads/
```

### Phase D — Frontend build

```bash
cd /var/www/azmus/app/frontend
npm ci
VITE_API_URL=https://api.azmus.uz npm run build
cp dist/* /var/www/azmus/frontend/   # or serve from app/frontend/dist
```

Write runtime config:

```bash
echo '{"apiUrl":"https://api.azmus.uz","updatedAt":"'$(date -Iseconds)'"}' \
  > /var/www/azmus/app/frontend/dist/remote-api.json
```

### Phase E — systemd services

Copy templates from `deploy/enterprise/systemd/`:

```bash
cp deploy/enterprise/systemd/azmus-api.service /etc/systemd/system/
cp deploy/enterprise/systemd/azmus-backup.timer /etc/systemd/system/
cp deploy/enterprise/systemd/azmus-backup.service /etc/systemd/system/
cp deploy/enterprise/systemd/azmus-healthcheck.timer /etc/systemd/system/
cp deploy/enterprise/systemd/azmus-healthcheck.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now azmus-api
systemctl enable --now azmus-backup.timer
systemctl enable --now azmus-healthcheck.timer
```

### Phase F — Nginx + SSL

```bash
cp deploy/enterprise/nginx/erp.azmus.uz.conf /etc/nginx/sites-available/
cp deploy/enterprise/nginx/api.azmus.uz.conf /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/erp.azmus.uz.conf /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/api.azmus.uz.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

certbot --nginx -d erp.azmus.uz -d api.azmus.uz
certbot renew --dry-run
```

### Phase G — Azmus Driver release APK

On build machine (Windows or CI):

```powershell
cd driver-app
# Set production API
"VITE_API_URL=https://api.azmus.uz" | Out-File .env.production -Encoding utf8
npm ci
npm run build
npx cap sync android
# Configure release keystore in android/app/build.gradle (signingConfigs)
cd android
./gradlew assembleRelease
```

Output: `driver-app/android/app/build/outputs/apk/release/app-release.apk`  
Publish: upload to `uploads/mobile/azmus-driver-release.apk` or distribute directly.

---

## 4. Migration checklist

### Pre-migration (Windows — local)

- [ ] Full backup: `D:\AzmusERP\Data\backups\manual\` (DB + uploads zip)
- [ ] Record row counts: orders, users, documents, mes_jobs, vehicles (`GET /` health)
- [ ] Export `.env` secrets list (JWT, Telegram) — rotate JWT for VPS
- [ ] Stop quick tunnel / avoid dual-write during cutover
- [ ] Document active users and scheduled jobs

### VPS preparation

- [ ] Ubuntu 24.04 provisioned, SSH hardened (key-only)
- [ ] DNS A records: `erp.azmus.uz`, `api.azmus.uz` → VPS IP
- [ ] PostgreSQL installed, `azmus_erp` database created
- [ ] `/var/lib/azmus/data` created with correct ownership
- [ ] Firewall: 80, 443 open; 5432 **localhost only**

### Data migration

- [ ] Copy `azmus.db` to VPS `migrations/`
- [ ] pgloader SQLite → PostgreSQL completed
- [ ] Verify counts match (orders=3+, users=9+, tables=74)
- [ ] rsync `uploads/` — verify file count and sample URLs
- [ ] Test login (admin) via `curl https://api.azmus.uz/auth/login`

### Application

- [ ] `DATABASE_URL` = PostgreSQL
- [ ] `DATABASE_GUARD=false` (SQLite guard not applicable)
- [ ] Backend starts: `systemctl status azmus-api`
- [ ] Frontend built with `VITE_API_URL=https://api.azmus.uz`
- [ ] SSL certificates valid (A+ on SSL Labs optional)
- [ ] CORS allows `https://erp.azmus.uz` only

### Functional smoke tests

- [ ] Login / logout on phone and desktop
- [ ] Orders list shows migrated orders
- [ ] Upload image (warehouse/LLP)
- [ ] MES terminal page loads
- [ ] GPS live map + driver APK → `POST /gps/location/update`
- [ ] Telegram test message from Settings
- [ ] Daily backup timer runs (check `/var/lib/azmus/data/backups/daily/`)

### Post-cutover

- [ ] Keep Windows SQLite read-only archive for 30 days
- [ ] Monitor logs 48h: `/var/lib/azmus/data/logs/`, `journalctl -u azmus-api`
- [ ] Update Azmus Driver APK server URL to `https://api.azmus.uz`
- [ ] Decommission trycloudflare tunnels

### Code changes required (repo — Phase Enterprise dev)

| Item | Status today | Action |
|------|--------------|--------|
| `psycopg2-binary` in requirements | Missing | Add |
| `run_migrations()` for Postgres | Skips non-SQLite | Port SQL or add Alembic |
| `auto_backup.py` | SQLite only | Add `pg_dump` path |
| `database_guard.py` | SQLite paths | Disable or Postgres-aware |
| Admin backup import/export | SQLite file | Add pg_dump restore |

---

## 5. Daily backup

**Schedule:** 02:00 Asia/Tashkent (matches current `BACKUP_HOUR=2`)

| Asset | Method | Path |
|-------|--------|------|
| PostgreSQL | `pg_dump -Fc` | `/var/lib/azmus/data/backups/daily/azmus_YYYYMMDD_HHMMSS.dump` |
| Uploads | `tar czf` | `/var/lib/azmus/data/backups/daily/uploads_YYYYMMDD.tar.gz` |
| Retention | 30 days | `find … -mtime +30 -delete` |

Script: `deploy/enterprise/scripts/daily_backup.sh`  
Restore DB: `pg_restore -d azmus_erp latest.dump`

**Off-site (recommended):** nightly `rclone` to S3 / Backblaze B2 / second VPS.

---

## 6. Monitoring — Telegram downtime alerts

**Health check:** every 2 minutes via systemd timer  
Script: `deploy/enterprise/scripts/healthcheck.sh`

- `GET https://api.azmus.uz/` → expect `"status":"ok"`
- `GET https://erp.azmus.uz/` → expect HTTP 200
- On 2 consecutive failures → send Telegram alert
- On recovery → send recovery message

Uses existing `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` from `/etc/azmus/.env`.

Optional upgrades:

- Uptime Kuma (self-hosted) on same or separate VPS
- PostgreSQL `pg_isready` check
- Disk space alert (>85%)

---

## 7. Estimated monthly cost

| Item | Low | Recommended |
|------|-----|-------------|
| VPS (4 vCPU / 8 GB) | $12–15 | $20–25 |
| Domain `.uz` (annual ÷12) | $1–3 | $2–4 |
| Backup storage (50 GB S3/B2) | $0–2 | $3–5 |
| Let's Encrypt SSL | $0 | $0 |
| Telegram Bot | $0 | $0 |
| **Total** | **~$15–20/mo** | **~$25–35/mo** |

One-time: Android release keystore (free), optional CI runner for APK builds.

**vs current:** Cloudflare quick tunnels = $0 but URLs expire, PC must stay on 24/7. VPS gives permanent `erp.azmus.uz` / `api.azmus.uz` and true 24/7.

---

## 8. Rollback plan

1. Stop `azmus-api` on VPS.
2. Point DNS back to Windows + Cloudflare tunnel (temporary).
3. Restore PostgreSQL from latest `pg_dump` if partial migration.
4. Windows SQLite at `D:\AzmusERP\Data\database\azmus.db` remains canonical archive until sign-off.

---

## 9. File templates in this folder

| File | Purpose |
|------|---------|
| `env.production.example` | VPS `/etc/azmus/.env` template |
| `nginx/erp.azmus.uz.conf` | SPA + SSL |
| `nginx/api.azmus.uz.conf` | API reverse proxy + uploads |
| `systemd/azmus-api.service` | uvicorn service |
| `systemd/azmus-backup.*` | daily backup timer |
| `systemd/azmus-healthcheck.*` | downtime Telegram alerts |
| `scripts/daily_backup.sh` | pg_dump + uploads tar |
| `scripts/healthcheck.sh` | API/UI probe + Telegram |

---

## 10. Timeline (suggested)

| Week | Milestone |
|------|-----------|
| 1 | VPS + Postgres + Nginx + SSL; SQLite via pgloader; smoke tests |
| 2 | Postgres-native backups, monitoring, driver release APK |
| 3 | Code hardening (Alembic, pg backup in app); decommission Windows tunnel |
| 4 | Load test, operator training, go-live sign-off |

**Go-live criterion:** Phone login at `https://erp.azmus.uz` shows same order count as local SQLite baseline.
