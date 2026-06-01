#!/usr/bin/env bash
set -euo pipefail

echo "Building Azmus ERP web assets..."
npm run build

echo "Syncing Capacitor Android project..."
npx cap sync android

echo "Building debug APK..."
cd android
./gradlew assembleDebug

echo "Done. APK is in android/app/build/outputs/apk/debug/"
