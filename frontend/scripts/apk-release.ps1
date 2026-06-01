$ErrorActionPreference = "Stop"

$adoptiumRoot = "C:\Program Files\Eclipse Adoptium"
$jdk21 = Get-ChildItem $adoptiumRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^jdk-21' } |
    Sort-Object Name -Descending |
    Select-Object -First 1
if ($jdk21) { $env:JAVA_HOME = $jdk21.FullName }
$env:ANDROID_HOME = "C:\Users\user\AppData\Local\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME

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
