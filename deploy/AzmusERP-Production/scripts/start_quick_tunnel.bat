@echo off
setlocal EnableDelayedExpansion
title Azmus ERP Quick Tunnel

REM Full setup: local DB + API tunnel + frontend build + UI tunnel.
REM Database: D:\AzmusERP\Data\database\azmus.db (never Render/cloud)

set "SCRIPT_DIR=%~dp0"
set "DB_PATH=D:\AzmusERP\Data\database\azmus.db"

if not exist "%DB_PATH%" (
  echo ERROR: Production database not found: %DB_PATH%
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_quick_tunnel.ps1"
if errorlevel 1 (
  echo.
  echo Quick tunnel failed. See D:\AzmusERP\Data\logs\
  pause
  exit /b 1
)

echo.
echo URLs saved to D:\AzmusERP\Data\logs\remote_access_urls.txt
pause
