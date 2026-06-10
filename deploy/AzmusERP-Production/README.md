# AzmusERP-Production deployment package

Copy the entire repository to `D:\AzmusERP\Application` and use scripts in this folder.

| Item | Location |
|------|----------|
| Environment template | `.env.production.template` |
| User guide | `USER_GUIDE.md` |
| Migrate data | `scripts\migrate_data_to_d.ps1` |
| Start / stop | `scripts\start_production.bat`, `stop_production.bat` |
| Remote access | `REMOTE_ACCESS.md`, `scripts\start_remote_access.bat` |
| APK build | `scripts\build_apk_production.ps1` → `apk\` |
| Audit tests | `scripts\run_production_audit.ps1` |

Data directory (default): `D:\AzmusERP\Data`

For internet access without moving the database, use Cloudflare Tunnel:

```powershell
.\scripts\build_remote_frontend.ps1 -ApiUrl "https://api-erp.YOUR_DOMAIN.com"
.\scripts\start_remote_access.bat
```

See `REMOTE_ACCESS.md` for Cloudflare Tunnel, Tailscale Funnel fallback, verification, and automatic startup.
