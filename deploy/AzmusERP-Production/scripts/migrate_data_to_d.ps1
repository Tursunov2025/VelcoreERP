# Migrate existing project data to D:\AzmusERP\Data (does NOT delete source files)
$ErrorActionPreference = "Stop"

$DataRoot = if ($env:DATA_ROOT) { $env:DATA_ROOT } else { "D:\AzmusERP\Data" }
$AppRoot = if ($env:APPLICATION_ROOT) { $env:APPLICATION_ROOT } else {
    $here = Split-Path $PSScriptRoot -Parent
    if (Test-Path (Join-Path $here "..\..\backend")) {
        (Resolve-Path (Join-Path $here "..\..")).Path
    } else {
        "D:\AzmusERP\Application"
    }
}

$Backend = Join-Path $AppRoot "backend"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$PreMigrateBackup = Join-Path $DataRoot "backups\pre_migrate_$stamp"

Write-Host "=== Azmus ERP data migration ===" 
Write-Host "Application: $AppRoot"
Write-Host "Data root:   $DataRoot"

$dirs = @(
    "$DataRoot\database",
    "$DataRoot\uploads",
    "$DataRoot\backups",
    "$DataRoot\logs",
    "$DataRoot\migrations",
    "$DataRoot\backups\daily"
)
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path $d | Out-Null }

New-Item -ItemType Directory -Force -Path $PreMigrateBackup | Out-Null

# Backup current production targets if they exist
$prodDb = "$DataRoot\database\azmus.db"
if (Test-Path $prodDb) {
    Copy-Item $prodDb (Join-Path $PreMigrateBackup "azmus.db.bak") -Force
    Write-Host "Backed up existing production DB"
}

# Database candidates (first found wins)
$dbSources = @(
    (Join-Path $Backend "azmus_new.db"),
    (Join-Path $Backend "database.db"),
    (Join-Path $AppRoot "database.db")
)
foreach ($src in $dbSources) {
    if (Test-Path $src) {
        Copy-Item $src $prodDb -Force
        Write-Host "Copied database: $src -> $prodDb"
        break
    }
}

# Uploads (LLP, branding, MES drawings live under uploads/)
$uploadSrc = Join-Path $Backend "uploads"
if (Test-Path $uploadSrc) {
    Write-Host "Copying uploads (merge)..."
    robocopy $uploadSrc "$DataRoot\uploads" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

# Legacy backups folder
$bakSrc = Join-Path $Backend "backups"
if (Test-Path $bakSrc) {
    Write-Host "Copying backups (merge)..."
    robocopy $bakSrc "$DataRoot\backups" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

# Frontend migration backups if present
$feBak = Join-Path $AppRoot "frontend\backups"
if (Test-Path $feBak) {
    robocopy $feBak "$DataRoot\migrations\frontend_import" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

Write-Host ""
Write-Host "DONE. Data is under $DataRoot"
Write-Host "Source files in the project were NOT deleted."
Write-Host "Pre-migration backup: $PreMigrateBackup"
Write-Host "Next: copy .env.production.template to Application\.env and run start_production.bat"
