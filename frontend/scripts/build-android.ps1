$ErrorActionPreference = "Stop"

Write-Host "Building Azmus ERP web assets..."
npm run build

Write-Host "Syncing Capacitor Android project..."
npx cap sync android

Write-Host "Building debug APK..."
Set-Location android
.\gradlew.bat assembleDebug

Write-Host "Done. APK is in android\app\build\outputs\apk\debug\"
