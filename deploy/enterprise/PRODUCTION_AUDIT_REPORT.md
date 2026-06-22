# Velcore ERP — Production Audit Report (2026-06-17)

Evidence-based audit of `https://erp.velcore.uz` and `https://api.velcore.uz`.

---

## 1. Login → `http://127.0.0.1:8000`

### A) API URL qayerdan keladi (100%)

| Qatlam | Fayl | Qator | Manba |
|--------|------|-------|-------|
| Build-time | `frontend/.env.production` | 2 | `VITE_API_URL` → Vite bundle ga yoziladi |
| Bundle | `dist/assets/index-*.js` | minified | `import.meta.env.VITE_API_URL` literal |
| Runtime (eski bundle) | `client.js` `ensureApiBase()` | 44–54 | `/remote-api.json` fetch |
| Runtime (yangi) | `client.js` `productionApiUrlFromHost()` | 7–12 | `erp.velcore.uz` hostname → `https://api.velcore.uz` |
| Fallback | `index.html` | meta | `<meta name="velcore-api-url" content="https://api.velcore.uz">` |

`frontend/src/config/*` — **mavjud emas**.

### B) Live production tekshiruv (fakt)

```
GET https://erp.velcore.uz/
→ <script src="/assets/index-DZyVg1r9.js">

GET https://erp.velcore.uz/assets/index-DZyVg1r9.js
→ FOUND: 127.0.0.1:8000
→ NOT FOUND: api.velcore.uz

GET https://erp.velcore.uz/remote-api.json
→ HTTP 200, body = index.html (SPA fallback)
```

**Root cause:** VPS da **eski build** (`index-DZyVg1r9.js`) xizmat qilmoqda. U `.env.production` da `VITE_API_URL=http://127.0.0.1:8000` bilan yig‘ilgan. Yangi build (`index-B_Gm2rgS.js`) VPS ga **deploy qilinmagan**.

Qoʻshimcha: Nginx `location /remote-api.json` SPA ga tushib, HTML qaytaradi — eski client JSON parse qila olmaydi, `127.0.0.1` da qoladi.

### C) Nginx root

`deploy/enterprise/nginx/erp.velcore.uz.conf` qator 19:

```nginx
root /var/www/velcore/frontend/dist;
```

Live HTML shu dist dan keladi (bundle nomi mos).

### D) API backend

```
GET https://api.velcore.uz/auth/login-users → 200 JSON (7 users)
```

API ishlayapti; muammo faqat frontend noto‘g‘ri URL ga murojaat qiladi.

### E) Tuzatishlar

| Fayl | O‘zgarish |
|------|-----------|
| `frontend/src/api/client.js` | `productionApiUrlFromHost()` — `erp.velcore.uz` da har doim `api.velcore.uz` |
| `frontend/index.html` | `velcore-api-url` meta |
| `frontend/.env.production` | `VITE_API_URL=https://api.velcore.uz` |
| `deploy/enterprise/nginx/erp.velcore.uz.conf` | `location = /remote-api.json { return 404; }` |
| `deploy/enterprise/scripts/build_frontend_production.sh` | Build + verify skript |

---

## 2. Hujjatlar (LLP) — O‘chirish

### A) Delete endpoint

`backend/routers/llp_router.py` qator **311–330**:

```
DELETE /llp/documents/{document_id}
```

### B) Frontend

`frontend/src/pages/LlpPage.jsx` qator **146–154**:

```javascript
await api.llpDeleteDocument(doc.id);
```

`frontend/src/api/client.js` qator **556**:

```javascript
llpDeleteDocument: (id) => request(`/llp/documents/${id}`, { method: "DELETE" })
```

### C) Live API

```
DELETE https://api.velcore.uz/llp/documents/1 → 401 (endpoint mavjud, auth kerak)
```

### D) Root cause

O‘chirish ham `request()` orqali **`API_BASE`** ga ketadi. Production bundle da `API_BASE = http://127.0.0.1:8000` → brauzer **mixed content** (HTTPS sahifa → HTTP localhost) bloklaydi → `"Server bilan bog'lanib bo'lmadi"`.

Yuklab olish / tahrirlash ham xuddi shu URL ishlatgan; ba’zi operatsiyalar cache yoki eski sessiya bilan ishlagan bo‘lishi mumkin. Asosiy tuzatish — to‘g‘ri API URL.

### E) Tuzatish

- `llpDeleteDocument` — `request()` (o‘zgarishsiz, URL tuzatilganda ishlaydi)
- `downloadDoc` — `apiDownload()` + `authenticatedFetch()` (to‘g‘ri base URL)

---

## 3. GPS moduli

### Routes (frontend)

| URL | Komponent | Holat |
|-----|-----------|-------|
| `/gps` | GpsMonitoringHubPage | ✅ |
| `/gps/monitoring` | LiveMapPage | ✅ |
| `/gps/transports` | TransportPage | ✅ |
| `/gps/vehicles` | VehiclesPage | ✅ |
| `/gps/drivers` | DriversPage | ✅ |
| `/gps/tasks` | TransportTasksPage | ✅ |
| `/driver` | DriverMobilePage | ✅ |

### API

| Endpoint | Holat |
|----------|-------|
| `POST /gps/update` | ✅ alias |
| `GET /gps/live` | ✅ alias |
| `GET /gps/history/{vehicle_id}` | ✅ alias |
| `GET/POST /gps/tasks` | ✅ |

### PostgreSQL jadvallar

`vehicles`, `drivers`, `gps_locations`, `transport_tasks` — `models.py` + `create_all()` / migration.

### Build

`npm run build` — ✅ muvaffaqiyatli (`index-B_Gm2rgS.js`).

---

## VPS deploy buyruqlari

```bash
cd /var/www/velcore
git pull origin main

# Nginx (remote-api.json fix)
sudo cp deploy/enterprise/nginx/erp.velcore.uz.conf /etc/nginx/sites-available/erp.velcore.uz
sudo nginx -t && sudo systemctl reload nginx

# Frontend rebuild + verify
sudo bash deploy/enterprise/scripts/build_frontend_production.sh

# Backend (agar kerak bo'lsa)
sudo systemctl restart velcore.service

# Tekshiruv
curl -s https://api.velcore.uz/auth/login-users | head -c 200
curl -sI https://erp.velcore.uz/remote-api.json   # 404 bo'lishi kerak
curl -s https://erp.velcore.uz/ | grep -o 'index-[^"]*\.js'
# Yangi hash: index-B_Gm2rgS.js (yoki keyingi build hash)
```

Brauzerda: DevTools → Network → `login-users` → `https://api.velcore.uz/auth/login-users`

Hard refresh: `Ctrl+Shift+R` (eski JS cache uchun).
