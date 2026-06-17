@echo off
REM Download cloudflared to D:\AzmusERP\tools if not in PATH
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ensure_cloudflared.ps1"
pause
