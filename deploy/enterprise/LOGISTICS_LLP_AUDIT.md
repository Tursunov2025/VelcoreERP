# Logistics & LLP Module Audit

**Date:** 2026-06-16  
**Project:** Velcore ERP

---

## Executive summary

Logistics menu restructured under **🚚 Logistika** with duplicate GPS/Transport entries removed. New backend module `/logistics/*` covers finished product warehouse, loading plans, barcode scan control, and GPS-linked shipment detail. LLP upload and delete paths fixed for production.

---

## 1. Logistics menu (FIXED)

### Before
- Duplicate entries: `/gps/*` and `/transport/*` mirrored Fleet Vehicles, Drivers, Live Map, Transport
- Section label: "Export va Logistika"

### After (`frontend/src/constants/workflow.js`)
```
🚚 Logistika
├ Dashboard                    /logistics
├ Tayyor Mahsulot Ombori       /logistics/finished-warehouse
├ Yuklash Rejalari             /logistics/loading-plans
├ Transportlar                 /logistics/transports
├ Haydovchilar                 /logistics/drivers
├ GPS Monitoring               /logistics/gps
├ Jonli Xarita                 /logistics/live-map
├ Yuklash Nazorati             /logistics/loading-control
├ Yo'ldagi Yuklar              /logistics/in-transit
├ Yetkazib Berilgan Yuklar     /logistics/delivered
└ LLP Hujjatlar                /logistics/llp
```

Legacy URLs redirect via `AppRouter.jsx` (`/gps`, `/transport` → `/logistics/*`).

---

## 2. Tayyor Mahsulot Ombori (NEW)

| Layer | File |
|-------|------|
| Model | `LogisticsFinishedProduct` in `backend/models.py` |
| API | `GET/POST /logistics/products`, `PUT /logistics/products/{id}` |
| UI | `frontend/src/pages/logistics/FinishedWarehousePage.jsx` |

Fields: `product_code`, `product_name`, `order_number`, `quantity`, `warehouse_location`, `status`, `barcode` (auto-generated).

Statuses: `Tayyor`, `Yuklanmoqda`, `Yuklandi`, `Yetkazildi`.

---

## 3. Yuklash Rejasi (NEW)

| Layer | File |
|-------|------|
| Models | `LogisticsLoadingShipment`, `LogisticsLoadingShipmentItem` |
| API | `/logistics/shipments`, `/logistics/shipments/{id}`, items, depart, deliver |
| UI | `LoadingPlansPage.jsx` — map on detail via `FleetMap` + GPS |

---

## 4. Yuklash Nazorati (NEW)

- `POST /logistics/loading/scan` — barcode → product → vehicle → driver → shipment
- Warehouse qty decremented; status updated
- UI: `LoadingControlPage.jsx`

---

## 5. GPS integratsiya (NEW)

- Shipment list/detail includes `gps_location` from `latest_location_for_vehicle()`
- `InTransitPage.jsx` — map + list
- `LoadingPlansPage.jsx` — map in shipment modal

---

## 6–8. LLP module fixes

### Issues found

| # | Issue | Root cause |
|---|--------|------------|
| 1 | Upload fails | Metadata sent as query string with `FormData`; some clients/proxies strip query on multipart POST |
| 2 | Delete FK violation | `export_shipment_documents.llp_document_id` FK without `ON DELETE SET NULL` |
| 3 | Wrong API URL (prod) | Stale frontend bundle / CORS (separate fix in `config/production.py`) |

### Fixes applied

| Fix | File |
|-----|------|
| Upload uses `Form()` fields | `backend/routers/llp_router.py` |
| Frontend FormData metadata | `frontend/src/api/client.js` — `llpUploadDocument` |
| FK unlink before delete | `llp_router.py` — nullify `export_shipment_documents` |
| FK `ON DELETE SET NULL` migration | `backend/database.py`, `models.py` |
| Disk write verification | `_save_llp_file()` — mkdir + exists check |

### LLP endpoints (verified)

- `POST /llp/documents` — multipart file + form fields
- `DELETE /llp/documents/{id}` — unlinks export refs, deletes file
- `GET /llp/documents/{id}/download` — FileResponse from `UPLOAD_PATH/llp/`

---

## 9. Migrations

Added to `backend/database.py` `run_migrations()`:

- `logistics_finished_products`
- `logistics_loading_shipments`
- `logistics_loading_shipment_items`
- Indexes on status, barcode
- (existing) `export_shipment_documents` FK `ON DELETE SET NULL`

**VPS:** `git pull` + `systemctl restart velcore.service` runs migrations on startup.

---

## 10. Files changed

### Backend
- `backend/models.py`
- `backend/routers/logistics_router.py` (new)
- `backend/routers/llp_router.py`
- `backend/database.py`
- `backend/main.py`

### Frontend
- `frontend/src/constants/workflow.js`
- `frontend/src/i18n/translations.js`
- `frontend/src/api/client.js`
- `frontend/src/AppRouter.jsx`
- `frontend/src/pages/logistics/*.jsx` (6 new pages)

### Deploy docs
- `deploy/enterprise/LOGISTICS_LLP_AUDIT.md` (this file)

---

## Suggested commit message

```
feat(logistics): restructure menu, add warehouse/loading module, fix LLP upload/delete

- Replace duplicate GPS/Transport nav with unified Logistika section
- Add /logistics API: finished products, loading shipments, barcode scan, GPS on detail
- Migrate logistics_finished_products, logistics_loading_shipments tables
- Fix LLP upload (Form fields + FormData), delete (FK SET NULL + unlink)
- Redirect legacy /gps and /transport routes to /logistics/*
```

---

## Post-deploy checklist

1. `cd /var/www/velcore && git pull && sudo systemctl restart velcore.service`
2. Rebuild frontend: `bash deploy/enterprise/scripts/build_frontend_production.sh`
3. Verify OpenAPI: `/logistics/dashboard`, `/logistics/products`
4. LLP: upload PDF → download → delete (no FK error)
5. Logistics: create product → create shipment → scan barcode
