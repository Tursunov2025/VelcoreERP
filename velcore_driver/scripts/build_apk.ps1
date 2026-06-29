# Velcore Driver — Release va Debug APK
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot/..

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Error "Flutter SDK topilmadi. https://docs.flutter.dev/get-started/install"
}

if (-not (Test-Path "android/gradlew.bat")) {
    Write-Host "flutter create ishga tushirilmoqda..."
    flutter create --org uz.velcore --project-name velcore_driver .
}

Write-Host "=== flutter pub get ==="
flutter pub get

$dest = "../deploy/AzmusERP-Production/apk"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

Write-Host "=== Release APK ==="
flutter build apk --release
$releaseApk = "build/app/outputs/flutter-apk/app-release.apk"
if (Test-Path $releaseApk) {
    Copy-Item $releaseApk "$dest/velcore-driver-1.0.0-release.apk" -Force
    Write-Host "Release: $dest/velcore-driver-1.0.0-release.apk"
}

Write-Host "=== Debug APK ==="
flutter build apk --debug
$debugApk = "build/app/outputs/flutter-apk/app-debug.apk"
if (Test-Path $debugApk) {
    Copy-Item $debugApk "$dest/velcore-driver-1.0.0-debug.apk" -Force
    Write-Host "Debug: $dest/velcore-driver-1.0.0-debug.apk"
}

Write-Host "Tayyor."
