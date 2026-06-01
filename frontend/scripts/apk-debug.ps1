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
if ($jdk21) {
    $env:JAVA_HOME = $jdk21.FullName
} elseif ($jdk17) {
    $env:JAVA_HOME = $jdk17.FullName
}
$env:ANDROID_HOME = "C:\Users\user\AppData\Local\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME

$localProps = Join-Path $PSScriptRoot "..\android\local.properties"
$sdkLine = "sdk.dir=C:\\Users\\user\\AppData\\Local\\Android\\Sdk"
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
