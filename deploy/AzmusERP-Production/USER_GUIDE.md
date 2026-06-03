# Azmus ERP — Production User Guide (1 month deployment)

## Folder layout

```
D:\AzmusERP\
├── Application\          ← copy this repo (code only)
│   ├── backend\
│   ├── frontend\
│   └── .env              ← from .env.production.template
└── Data\                 ← ALL business data (never inside Application)
    ├── database\azmus.db
    ├── uploads\          ← LLP, branding, MES files
    ├── backups\daily\    ← auto backups (30 days)
    ├── logs\
    └── migrations\
```

## First-time setup

1. Copy project to `D:\AzmusERP\Application`
2. Copy `deploy\AzmusERP-Production\.env.production.template` → `D:\AzmusERP\Application\.env`
3. Set a strong `JWT_SECRET_KEY` in `.env`
4. Run `scripts\migrate_data_to_d.ps1` (copies existing DB/uploads; does not delete sources)
5. Run `scripts\start_production.bat`

## Daily use

| Action | Script |
|--------|--------|
| Start servers | `scripts\start_production.bat` |
| Stop servers | `scripts\stop_production.bat` |
| Manual backup | `scripts\run_daily_backup.bat` |

Automatic backup runs daily at 02:00 (server time) when backend is running.

## Access URLs

After start, the console shows:

- **This PC:** http://localhost:5173
- **LAN / phones:** http://SERVER-IP:5173 (same Wi‑Fi)
- **API:** http://SERVER-IP:8000

Allow Windows Firewall for ports **8000** and **5173** on Private networks.

## Android APK

1. Set server IP in `.env`: `VITE_API_URL=http://192.168.x.x:8000`
2. Run `scripts\build_apk_production.ps1`
3. Install `apk\azmus-erp-1.0.0-debug.apk` on phones
4. Phone must be on same Wi‑Fi as server

## Restart after reboot

1. `start_production.bat` (runs in background; survives browser close)
2. Verify http://localhost:5173 and admin login

## Restore database backup

1. Stop production (`stop_production.bat`)
2. Copy a file from `D:\AzmusERP\Data\backups\daily\azmus_YYYYMMDD_HHMMSS.db`
3. From `backend` folder:
   ```powershell
   python -c "from pathlib import Path; from services.auto_backup import restore_database_from_backup; print(restore_database_from_backup(Path(r'D:\AzmusERP\Data\backups\daily\azmus_YYYYMMDD_HHMMSS.db')))"
   ```
4. `start_production.bat`

## Admin login (seed)

Default after seed: `admin` / `1234` — change password immediately in Settings → Users.

## Support checks

- Logs: `D:\AzmusERP\Data\logs\azmus-backend.log`
- Health: http://localhost:8000/
- API docs (non-prod only): http://localhost:8000/docs
