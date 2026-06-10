$ErrorActionPreference = "Stop"

Write-Host "Starting Azmus ERP local services first..."
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartScript = Join-Path $ScriptDir "scripts\start_production.bat"
Start-Process -FilePath $StartScript

Write-Host "Waiting for local frontend..."
Start-Sleep -Seconds 8

Write-Host "Starting Tailscale Funnel for the frontend on localhost:5173..."
Write-Host "The backend remains local at D:\AzmusERP\Data\database\azmus.db."
Write-Host ""
Write-Host "Note: Build the frontend with an API URL reachable from the browser."
Write-Host "For simple Tailscale private access, prefer Tailscale Serve/Funnel rules for both 5173 and 8000."

tailscale funnel --bg 5173
tailscale funnel status

