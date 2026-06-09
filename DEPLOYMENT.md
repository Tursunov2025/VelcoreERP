# Azmus CRM ERP — Production deployment

## Live services

| Service | URL |
|---------|-----|
| **API** | https://azmus-crm.onrender.com |
| **Frontend** | Deploy `frontend/dist` to Render Static Site, Netlify, or Vercel |

## ERP modules

- **Dashboard** — analytics, charts, KPIs
- **Zakazlar** — orders with images, production stages
- **Ishlab chiqarish** — timeline, stage tracking
- **Ombor** — materials, stock in/out, low-stock alerts
- **Operatorlar** — performance rankings
- **Analitika** — sales, revenue, profit charts
- **Moliya** — income, expenses, net profit
- **Invoyslar** — PDF export with QR + barcode
- **JWT auth** — access + refresh tokens, role-based access
- **Telegram** — optional notifications (env vars below)

## Mobile / global access

1. Host the **frontend** on a public HTTPS URL (not `localhost`).
2. The app calls **https://azmus-crm.onrender.com** (set in `frontend/.env` as `VITE_API_URL`).
3. Any phone on Wi‑Fi or mobile data can open the frontend URL in a browser.

Default logins (seeded on API startup):

- Admin: `admin` / `1234`
- Operator: `operator1` / `1111`

## Build frontend for production

```bash
cd frontend
npm install
npm run build
```

Output: `frontend/dist/` — upload or connect to your static host.

## Deploy API (Render)

From repo root, use `render.yaml` or configure manually:

- **Root directory:** `backend`
- **Build:** `pip install -r requirements.txt`
- **Start:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health check:** `/`

**Environment variables (API service):**

| Variable | Value |
|----------|--------|
| `ENVIRONMENT` | `production` |
| `DATA_ROOT` | `/opt/render/project/data` |
| `DB_PATH` | `/opt/render/project/data/database/azmus.db` |
| `UPLOAD_PATH` | `/opt/render/project/data/uploads` |
| `BACKUP_PATH` | `/opt/render/project/data/backups` |
| `LOG_PATH` | `/opt/render/project/data/logs` |
| `MIGRATION_BACKUP_PATH` | `/opt/render/project/data/migrations` |
| `DATABASE_GUARD` | `true` — **blocks startup if DB is missing or below production baseline** |
| `SKIP_DEMO_SEED` | `true` — do not recreate demo operators on empty DB |
| `CORS_ORIGINS` | `*` (allows any frontend origin) or comma-separated URLs |
| `JWT_SECRET_KEY` | Strong random secret for production |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather (optional) |
| `TELEGRAM_CHAT_ID` | Admin chat/group ID (optional) |

**Persistent disk (required):** attach a disk in `render.yaml` (or Dashboard → Disks):

- **Mount path:** `/opt/render/project/data`
- **Size:** 1 GB minimum

Only files under the disk mount path survive redeploys. Without a disk, each deploy creates a fresh empty SQLite file and the UI appears empty after import.

**Re-import production data to Render:**

```bash
cd backend
python scripts/sync_production_to_render.py
```

Local source: `D:\AzmusERP\Data\database\azmus.db` (never overwritten by the script).

## Deploy frontend (Render Static Site)

- **Root directory:** `frontend`
- **Build:** `npm install && npm run build`
- **Publish directory:** `dist`
- **Environment:** `VITE_API_URL=https://azmus-crm.onrender.com`
- **SPA rewrite:** `/*` → `/index.html`

## Local development

```bash
# frontend/.env
VITE_API_URL=http://127.0.0.1:8000
```

Restart `npm run dev` after changing `.env`.
