@echo off
setlocal EnableDelayedExpansion
title Azmus ERP Remote Access (Named Tunnel)

set "SCRIPT_DIR=%~dp0"
set "APP_ROOT=%SCRIPT_DIR%..\..\..\"
if exist "D:\AzmusERP\Application\backend\main.py" set "APP_ROOT=D:\AzmusERP\Application\"

set "DATA_ROOT=D:\AzmusERP\Data"
set "DB_PATH=D:\AzmusERP\Data\database\azmus.db"
set "LOG_PATH=D:\AzmusERP\Data\logs"
set "CLOUDFLARED=D:\AzmusERP\tools\cloudflared.exe"

if not exist "%DB_PATH%" (
  echo ERROR: Production database not found: %DB_PATH%
  pause
  exit /b 1
)

if not exist "%LOG_PATH%" mkdir "%LOG_PATH%"

REM Ensure cloudflared exists
if not exist "%CLOUDFLARED%" (
  echo Installing cloudflared to D:\AzmusERP\tools ...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%ensure_cloudflared.ps1"
)

where cloudflared >nul 2>nul
if errorlevel 1 (
  set "CF=%CLOUDFLARED%"
) else (
  set "CF=cloudflared"
)

if not exist "%USERPROFILE%\.cloudflared\config.yml" (
  echo.
  echo ERROR: Named Cloudflare tunnel is not configured.
  echo Missing: %USERPROFILE%\.cloudflared\config.yml
  echo.
  echo For immediate access WITHOUT Cloudflare account, use instead:
  echo   %SCRIPT_DIR%start_quick_tunnel.bat
  echo.
  echo To set up named tunnel ^(permanent URL^):
  echo   1. "%CF%" tunnel login
  echo   2. "%CF%" tunnel create azmus-erp
  echo   3. Copy cloudflared-config.example.yml to %USERPROFILE%\.cloudflared\config.yml
  echo.
  pause
  exit /b 1
)

for /f %%i in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%get_lan_ip.ps1"') do set LAN_IP=%%i

if not exist "%APP_ROOT%backend\main.py" (
  echo ERROR: backend\main.py not found under %APP_ROOT%
  pause
  exit /b 1
)

cd /d "%APP_ROOT%frontend"
if not exist "dist\index.html" (
  echo Building frontend ...
  call npm run build
  if errorlevel 1 exit /b 1
)

echo Starting backend on 0.0.0.0:8000 ...
start "Azmus-Backend" /MIN cmd /c "cd /d %APP_ROOT%backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 >> %LOG_PATH%\uvicorn.out.log 2>>&1"
timeout /t 3 /nobreak >nul

echo Starting frontend on 0.0.0.0:5173 ...
start "Azmus-Frontend" /MIN cmd /c "cd /d %APP_ROOT%frontend && npm run preview:prod >> %LOG_PATH%\vite-preview.out.log 2>>&1"

echo Starting named Cloudflare tunnel ...
start "Azmus-Cloudflare-Tunnel" /MIN cmd /c ""%CF%" tunnel run azmus-erp >> %LOG_PATH%\cloudflared.out.log 2>>&1"

echo.
echo ============================================
echo   Azmus ERP Remote Access
echo ============================================
echo   Database:  %DB_PATH%
echo   Local UI:  http://127.0.0.1:5173
echo   Local API: http://127.0.0.1:8000
echo   LAN UI:    http://!LAN_IP!:5173
echo   Public:    see your config.yml hostnames
echo ============================================
pause
