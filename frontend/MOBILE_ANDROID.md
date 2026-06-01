# Azmus ERP Android Build Guide

## App Identity
- App name: `Azmus ERP`
- Package ID: `com.azmus.erp`

## First-time Setup
1. Install Node.js LTS
2. Install Android Studio (SDK + Platform Tools)
3. Install **JDK 21** (required by Capacitor 8 plugins)
4. SDK path is auto-configured in `android/local.properties`:
   - `sdk.dir=C:\\Users\\user\\AppData\\Local\\Android\\Sdk`

## Commands
- Build web + sync native project:
  - `npm run mobile:build`
- Open Android Studio:
  - `npm run mobile:open`
- Build debug APK (CLI, sets JAVA_HOME + ANDROID_HOME automatically):
  - `npm run apk:debug`
- Debug APK output:
  - `android/app/build/outputs/apk/debug/app-debug.apk`
- Build release APK (CLI):
  - `npm run apk:release`

## Icons and Splash
- Source files are under `resources/`
- Regenerate native assets:
  - `npm run mobile:assets`

## Push Notifications
- Capacitor push registration is initialized in `src/mobile/capacitor.js`
- Firebase/FCM configuration is required before publishing:
  - add `google-services.json` into `android/app/`
  - configure Firebase project + sender ID

## Google Play Release Checklist
1. Configure release keystore in Android Studio/Gradle
2. Increase `versionCode` and `versionName`
3. Build signed AAB from Android Studio
4. Upload to Google Play Console
5. Fill Data Safety and permissions declarations
6. Verify notification and camera permission flows on Android 13+
