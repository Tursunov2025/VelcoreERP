@echo off
setlocal
set "APP_ROOT=%~dp0..\..\..\"
if exist "D:\AzmusERP\Application\backend\main.py" set "APP_ROOT=D:\AzmusERP\Application\"

cd /d "%APP_ROOT%backend"
if exist "%APP_ROOT%.env" set AZMUS_ENV_FILE=%APP_ROOT%.env
if exist "%APP_ROOT%backend\.env" set AZMUS_ENV_FILE=%APP_ROOT%backend\.env

python -c "from services.auto_backup import run_daily_backup; import json; print(json.dumps(run_daily_backup(), indent=2))"
echo Backup finished. Check D:\AzmusERP\Data\backups\daily
pause
