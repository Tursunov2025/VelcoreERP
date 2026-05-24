# Azmus CRM — Production deployment

## Live services

| Service | URL |
|---------|-----|
| **API** | https://azmus-crm.onrender.com |
| **Frontend** | Deploy `frontend/dist` to Render Static Site, Netlify, or Vercel |

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

**Environment variables:**

| Variable | Value |
|----------|--------|
| `CORS_ORIGINS` | `*` (allows any frontend origin) or comma-separated URLs |

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
