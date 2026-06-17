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
$localProps = Join-Path $Android "local.properties"
$sdkLine = "sdk.dir=$($env:ANDROID_HOME -replace '\\','\\')"
if (-not (Test-Path $localProps)) {
    Set-Content -Path $localProps -Value $sdkLine -Encoding ASCII
}

Write-Host "Building Azmus Driver web bundle..."
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
    .\gradlew.bat assembleDebug --no-daemon
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $apk = Join-Path $Android "app\build\outputs\apk\debug\app-debug.apk"
    if (-not (Test-Path $apk)) { throw "APK not found: $apk" }

    $outDir = Resolve-Path (Join-Path $Root "..\deploy\AzmusERP-Production\apk") -ErrorAction SilentlyContinue
    if (-not $outDir) {
        $outDir = Join-Path $Root "..\deploy\AzmusERP-Production\apk"
        New-Item -ItemType Directory -Force -Path $outDir | Out-Null
        $outDir = Resolve-Path $outDir
    }
    $dest = Join-Path $outDir "azmus-driver-1.0.0-debug.apk"
    Copy-Item $apk $dest -Force
    Write-Host ""
    Write-Host "BUILD SUCCESSFUL"
    Write-Host "APK: $dest"
} finally {
    Pop-Location
}
