$ErrorActionPreference = "Stop"

$adoptiumRoot = "C:\Program Files\Eclipse Adoptium"
$jdk21 = Get-ChildItem $adoptiumRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^jdk-21' } |
    Sort-Object Name -Descending |
    Select-Object -First 1
$jdk17 = Get-ChildItem $adoptiumRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^jdk-17' } |
    Sort-Object Name -Descending |
    Select-Object -First 1
if ($jdk21) { $env:JAVA_HOME = $jdk21.FullName }
elseif ($jdk17) { $env:JAVA_HOME = $jdk17.FullName }

$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME

$Root = Split-Path -Parent $PSScriptRoot
$Android = Join-Path $Root "android"
$sdkLine = "sdk.dir=$($env:ANDROID_HOME -replace '\\','\\')"
Set-Content -Path (Join-Path $Android "local.properties") -Value $sdkLine -Encoding ASCII

Write-Host "Building Velcore Driver web bundle (production API)..."
Push-Location $Root
try {
    if (-not (Test-Path "node_modules")) { npm install }
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npx cap sync android
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

Write-Host "JAVA_HOME=$env:JAVA_HOME"
Write-Host "ANDROID_HOME=$env:ANDROID_HOME"

Push-Location $Android
try {
    .\gradlew.bat assembleRelease --no-daemon
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $unsigned = Join-Path $Android "app\build\outputs\apk\release\app-release-unsigned.apk"
    $signed = Join-Path $Android "app\build\outputs\apk\release\app-release.apk"
    if (-not (Test-Path $unsigned)) { throw "APK not found: $unsigned" }

    $buildTools = Get-ChildItem "$env:ANDROID_HOME\build-tools" -Directory |
        Sort-Object Name -Descending |
        Select-Object -First 1
    $apksigner = Join-Path $buildTools.FullName "apksigner.bat"
    $debugKs = Join-Path $env:USERPROFILE ".android\debug.keystore"
    if ((Test-Path $apksigner) -and (Test-Path $debugKs)) {
        & $apksigner sign --ks $debugKs --ks-pass pass:android --key-pass pass:android `
            --out $signed $unsigned
    } else {
        Copy-Item $unsigned $signed -Force
        Write-Warning "Debug keystore not found — unsigned APK copied (may not install on device)."
    }

    $outDir = Join-Path $Root "..\deploy\AzmusERP-Production\apk"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $dest = Join-Path $outDir "velcore-driver-1.0.0-release.apk"
    Copy-Item $signed $dest -Force
    Write-Host ""
    Write-Host "BUILD SUCCESSFUL"
    Write-Host "APK: $dest"
    Write-Host "Gradle: $signed"
} finally {
    Pop-Location
}
