# Local dev server — kills stale listeners on :8000 and excludes SQLite sidecar files
# from uvicorn reload (WAL/SHM writes otherwise trigger endless worker restarts).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

foreach ($conn in Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    $procId = $conn.OwningProcess
    if ($procId) {
        Write-Host "Stopping process $procId listening on :8000"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 1

if (-not $env:JWT_SECRET_KEY) {
    Write-Host "JWT_SECRET_KEY is not set - login will fail until you export it."
}

$uvicornArgs = @(
    "main:app",
    "--reload",
    "--host", "127.0.0.1",
    "--port", "8000",
    "--reload-exclude", "azmus_new.db*",
    "--reload-exclude", "*.db",
    "--reload-exclude", "*.db-wal",
    "--reload-exclude", "*.db-shm",
    "--reload-exclude", "__pycache__"
)

uvicorn @uvicornArgs
