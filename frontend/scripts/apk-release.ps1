$ErrorActionPreference = "Stop"

$frontendRoot = Join-Path $PSScriptRoot ".."
Push-Location $frontendRoot
try {
    Write-Host "Building web assets for production..."
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Syncing Capacitor Android project..."
    npx cap sync android
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

$adoptiumRoot = "C:\Program Files\Eclipse Adoptium"
$jdk21 = Get-ChildItem $adoptiumRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^jdk-21' } |
    Sort-Object Name -Descending |
    Select-Object -First 1
if ($jdk21) { $env:JAVA_HOME = $jdk21.FullName }
$env:ANDROID_HOME = "C:\Users\user\AppData\Local\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME

$localProps = Join-Path $PSScriptRoot "..\android\local.properties"
$sdkLine = "sdk.dir=C:\\Users\\user\\AppData\\Local\\Android\\Sdk"
if (-not (Test-Path $localProps) -or -not (Select-String -Path $localProps -Pattern "sdk.dir" -Quiet)) {
    Set-Content -Path $localProps -Value $sdkLine -Encoding ASCII
}

Push-Location (Join-Path $PSScriptRoot "..\android")
try {
    .\gradlew.bat assembleRelease --no-daemon
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $apk = Resolve-Path "app\build\outputs\apk\release\app-release-unsigned.apk" -ErrorAction SilentlyContinue
    if ($apk) {
        Write-Host ""
        Write-Host "BUILD SUCCESSFUL"
        Write-Host "APK: $($apk.Path)"
    }
} finally {
    Pop-Location
}
