# Build debug + release APK with production API URL (LAN server)
param(
    [string]$ApiUrl = "",
    [string]$AppRoot = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
if (-not $AppRoot) {
    $AppRoot = Resolve-Path (Join-Path $ScriptDir "..\..\..")
    if (-not (Test-Path (Join-Path $AppRoot "frontend"))) {
        $AppRoot = "D:\AzmusERP\Application"
    }
}

$Frontend = Join-Path $AppRoot "frontend"
if (-not $ApiUrl) {
    $ip = & (Join-Path $ScriptDir "get_lan_ip.ps1")
    $ApiUrl = "http://${ip}:8000"
}

Write-Host "API URL for APK: $ApiUrl"
$envFile = Join-Path $Frontend ".env.production.local"
"VITE_API_URL=$ApiUrl" | Set-Content -Path $envFile -Encoding UTF8

Push-Location $Frontend
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npx cap sync android
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

$Android = Join-Path $Frontend "android"
# capacitor-assets may leave duplicate .png + .webp launcher files
Get-ChildItem (Join-Path $Android "app\src\main\res") -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^ic_launcher(\.png|_foreground\.png|_round\.png)$' } |
    ForEach-Object {
        $webp = $_.FullName -replace '\.png$', '.webp'
        if (Test-Path $webp) { Remove-Item $_.FullName -Force }
    }
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME

Push-Location $Android
try {
    .\gradlew.bat assembleDebug assembleRelease --no-daemon
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

$outDir = Join-Path $AppRoot "deploy\AzmusERP-Production\apk"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$debugApk = Join-Path $Android "app\build\outputs\apk\debug\app-debug.apk"
$releaseApk = Join-Path $Android "app\build\outputs\apk\release\app-release-unsigned.apk"
if (Test-Path $debugApk) {
    Copy-Item $debugApk (Join-Path $outDir "azmus-erp-1.0.0-debug.apk") -Force
    Write-Host "Debug APK: $(Join-Path $outDir 'azmus-erp-1.0.0-debug.apk')"
}
if (Test-Path $releaseApk) {
    Copy-Item $releaseApk (Join-Path $outDir "azmus-erp-1.0.0-release-unsigned.apk") -Force
    Write-Host "Release APK: $(Join-Path $outDir 'azmus-erp-1.0.0-release-unsigned.apk')"
}

Write-Host "Done. Install debug APK on phones; point API to $ApiUrl"
