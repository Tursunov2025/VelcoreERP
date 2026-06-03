# Full module smoke tests + backup test (no data deletion)
$ErrorActionPreference = "Stop"
$AppRoot = if (Test-Path "D:\AzmusERP\Application\backend") { "D:\AzmusERP\Application" } else { (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path }
$Backend = Join-Path $AppRoot "backend"

$env:JWT_SECRET_KEY = if ($env:JWT_SECRET_KEY) { $env:JWT_SECRET_KEY } else { "audit-test-secret" }

$tests = @(
    "test_p4_a1_materials.py",
    "test_p4_a2_material_consumption.py",
    "test_p4_a3_auto_consumption.py",
    "test_p5_central_settings.py",
    "test_p6_control_center.py",
    "test_b5_qc_terminal.py",
    "test_b6_packaging_terminal.py",
    "test_b7_warehouse_terminal.py",
    "test_b8_dispatch_terminal.py",
    "test_production_backup.py"
)

Push-Location $Backend
$failed = @()
foreach ($t in $tests) {
    Write-Host "`n=== $t ===" -ForegroundColor Cyan
    python $t
    if ($LASTEXITCODE -ne 0) { $failed += $t }
}
Write-Host "`n=== Import main (materials routes) ===" -ForegroundColor Cyan
python -c "from main import app; m=[r.path for r in app.routes if r.path.startswith('/materials')]; print('materials routes:', len(m)); assert len(m)>=10"
if ($LASTEXITCODE -ne 0) { $failed += "main_import" }

Pop-Location

if ($failed.Count) {
    Write-Host "FAILED:" $failed -ForegroundColor Red
    exit 1
}
Write-Host "`nALL PRODUCTION AUDIT TESTS PASSED" -ForegroundColor Green
