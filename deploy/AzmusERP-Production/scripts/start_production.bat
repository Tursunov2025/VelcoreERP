@echo off
setlocal EnableDelayedExpansion
title Azmus ERP Production

REM Resolve application root (deployed layout or dev repo)
set "SCRIPT_DIR=%~dp0"
set "APP_ROOT=%SCRIPT_DIR%..\..\..\"
if exist "D:\AzmusERP\Application\backend\main.py" set "APP_ROOT=D:\AzmusERP\Application\"

cd /d "%APP_ROOT%"
if not exist "backend\main.py" (
  echo ERROR: backend\main.py not found in %APP_ROOT%
  pause
  exit /b 1
)

REM Load .env into process for child shells
if exist "%APP_ROOT%backend\.env" copy /Y "%APP_ROOT%backend\.env" "%APP_ROOT%backend\.env.loaded" >nul
if exist "%APP_ROOT%.env" (
  echo Using %APP_ROOT%.env
) else if exist "%APP_ROOT%backend\.env" (
  echo Using %APP_ROOT%backend\.env
) else (
  echo WARNING: No .env file. Copy .env.production.template to Application\.env
)

for /f %%i in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%get_lan_ip.ps1"') do set LAN_IP=%%i

echo.
echo ============================================
echo   Azmus ERP Production Server
echo ============================================
echo   PC browser:    http://localhost:5173
echo   LAN / phones:  http://!LAN_IP!:5173
echo   API:           http://!LAN_IP!:8000
echo ============================================
echo.
echo Logs: D:\AzmusERP\Data\logs\
echo Data: D:\AzmusERP\Data\
echo.
echo Close this window to keep servers running in background.
echo Use stop_production.bat to stop services.
echo.

set JWT_SECRET_KEY=
if exist "%APP_ROOT%backend\.env" (
  for /f "usebackq tokens=1,* delims==" %%a in ("%APP_ROOT%backend\.env") do (
    if /i "%%a"=="JWT_SECRET_KEY" set JWT_SECRET_KEY=%%b
  )
)
if "!JWT_SECRET_KEY!"=="" if exist "%APP_ROOT%.env" (
  for /f "usebackq tokens=1,* delims==" %%a in ("%APP_ROOT%.env") do (
    if /i "%%a"=="JWT_SECRET_KEY" set JWT_SECRET_KEY=%%b
  )
)

cd /d "%APP_ROOT%frontend"
if not exist "dist\index.html" (
  echo Building frontend...
  call npm run build
  if errorlevel 1 exit /b 1
)

echo Starting backend on 0.0.0.0:8000 ...
start "Azmus-Backend" /MIN cmd /c "cd /d %APP_ROOT%backend && set AZMUS_ENV_FILE=%APP_ROOT%backend\.env && if exist %APP_ROOT%.env set AZMUS_ENV_FILE=%APP_ROOT%.env && python -m uvicorn main:app --host 0.0.0.0 --port 8000 >> D:\AzmusERP\Data\logs\uvicorn.out.log 2>>&1"

timeout /t 3 /nobreak >nul

echo Starting frontend on 0.0.0.0:5173 ...
start "Azmus-Frontend" /MIN cmd /c "cd /d %APP_ROOT%frontend && npm run preview:prod >> D:\AzmusERP\Data\logs\vite-preview.out.log 2>>&1"

echo !LAN_IP!> "%SCRIPT_DIR%..\last_lan_ip.txt"
echo.
echo Servers started. Open http://!LAN_IP!:5173 from other devices on Wi-Fi.
echo.
pause
