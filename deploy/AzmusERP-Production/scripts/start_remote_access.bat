@echo off
setlocal EnableDelayedExpansion
title Azmus ERP Remote Access

set "SCRIPT_DIR=%~dp0"
set "APP_ROOT=%SCRIPT_DIR%..\..\..\"
if exist "D:\AzmusERP\Application\backend\main.py" set "APP_ROOT=D:\AzmusERP\Application\"

set "DATA_ROOT=D:\AzmusERP\Data"
set "DB_PATH=D:\AzmusERP\Data\database\azmus.db"
set "UPLOAD_PATH=D:\AzmusERP\Data\uploads"
set "BACKUP_PATH=D:\AzmusERP\Data\backups"
set "LOG_PATH=D:\AzmusERP\Data\logs"
set "MIGRATION_BACKUP_PATH=D:\AzmusERP\Data\migrations"
set "DATABASE_GUARD=true"
set "SKIP_DEMO_SEED=true"
set "ENVIRONMENT=production"

if not exist "%DB_PATH%" (
  echo ERROR: Production database not found:
  echo   %DB_PATH%
  echo Refusing to start remote access on an empty database.
  pause
  exit /b 1
)

if not exist "%LOG_PATH%" mkdir "%LOG_PATH%"

where cloudflared >nul 2>nul
if errorlevel 1 (
  echo ERROR: cloudflared.exe was not found in PATH.
  echo Install Cloudflare Tunnel, then run:
  echo   cloudflared tunnel login
  echo   cloudflared tunnel create azmus-erp
  pause
  exit /b 1
)

for /f %%i in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%get_lan_ip.ps1"') do set LAN_IP=%%i

echo.
echo ============================================
echo   Azmus ERP Remote Access
echo ============================================
echo   Data:         %DATA_ROOT%
echo   Database:     %DB_PATH%
echo   Office LAN:   http://!LAN_IP!:5173
echo   Local API:    http://!LAN_IP!:8000
echo   Tunnel:       cloudflared tunnel run azmus-erp
echo ============================================
if not exist "%APP_ROOT%backend\main.py" (
  echo ERROR: backend\main.py not found under %APP_ROOT%
  pause
  exit /b 1
)

cd /d "%APP_ROOT%frontend"
if not exist "dist\index.html" (
  echo ERROR: frontend\dist\index.html not found.
  echo Build the remote frontend first, for example:
  echo   powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_remote_frontend.ps1" -ApiUrl "https://api-erp.YOUR_DOMAIN.com"
  pause
  exit /b 1
)

echo Starting backend on 0.0.0.0:8000 ...
start "Azmus-Backend" /MIN cmd /c "cd /d %APP_ROOT%backend && set AZMUS_ENV_FILE=%APP_ROOT%backend\.env && if exist %APP_ROOT%.env set AZMUS_ENV_FILE=%APP_ROOT%.env && python -m uvicorn main:app --host 0.0.0.0 --port 8000 >> %LOG_PATH%\uvicorn.out.log 2>>&1"

timeout /t 3 /nobreak >nul

echo Starting frontend on 0.0.0.0:5173 ...
start "Azmus-Frontend" /MIN cmd /c "cd /d %APP_ROOT%frontend && npm run preview:prod >> %LOG_PATH%\vite-preview.out.log 2>>&1"

echo !LAN_IP!> "%SCRIPT_DIR%..\last_lan_ip.txt"

echo Starting Cloudflare Tunnel ...
start "Azmus-Cloudflare-Tunnel" /MIN cmd /c "cloudflared tunnel run azmus-erp >> %LOG_PATH%\cloudflared.out.log 2>>&1"

echo.
echo Remote access startup requested.
echo Public URL is the hostname configured in cloudflared config.yml, for example:
echo   https://erp.YOUR_DOMAIN.com
echo.
pause

