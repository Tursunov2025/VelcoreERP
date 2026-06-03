# AzmusERP-Production deployment package

Copy the entire repository to `D:\AzmusERP\Application` and use scripts in this folder.

| Item | Location |
|------|----------|
| Environment template | `.env.production.template` |
| User guide | `USER_GUIDE.md` |
| Migrate data | `scripts\migrate_data_to_d.ps1` |
| Start / stop | `scripts\start_production.bat`, `stop_production.bat` |
| APK build | `scripts\build_apk_production.ps1` → `apk\` |
| Audit tests | `scripts\run_production_audit.ps1` |

Data directory (default): `D:\AzmusERP\Data`
