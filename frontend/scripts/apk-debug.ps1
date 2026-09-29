$ErrorActionPreference = "Stop"

$jdk21 = Get-Item "$env:USERPROFILE\.jdks\jbr-21.0.11"


if ($jdk21) {
    $env:JAVA_HOME = $jdk21.FullName
} elseif ($jdk17) {
    $env:JAVA_HOME = $jdk17.FullName
}
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME

$localProps = Join-Path $PSScriptRoot "..\android\local.properties"
$sdkLine = "sdk.dir=$($env:LOCALAPPDATA -replace '\\','/')/Android/Sdk"
if (-not (Test-Path $localProps) -or -not (Select-String -Path $localProps -Pattern "sdk.dir" -Quiet)) {
    Set-Content -Path $localProps -Value $sdkLine -Encoding ASCII
}

Write-Host "JAVA_HOME=$env:JAVA_HOME"
Write-Host "ANDROID_HOME=$env:ANDROID_HOME"
Write-Host "SDK exists: $(Test-Path $env:ANDROID_HOME)"

Push-Location (Join-Path $PSScriptRoot "..\android")
try {
    .\gradlew.bat assembleDebug --no-daemon
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $apk = Resolve-Path "app\build\outputs\apk\debug\app-debug.apk" -ErrorAction SilentlyContinue
    if ($apk) {
        Write-Host ""
        Write-Host "BUILD SUCCESSFUL"
        Write-Host "APK: $($apk.Path)"
    }
} finally {
    Pop-Location
}

