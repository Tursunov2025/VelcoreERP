# Azmus Driver — Release APK build (production API)

## Prerequisites

- JDK 21
- Android SDK
- Release keystore (create once, store securely)

## 1. Create keystore (once)

```bash
keytool -genkey -v -keystore azmus-driver-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias azmus-driver
```

Store `azmus-driver-release.jks` **outside git**. Reference from `driver-app/android/keystore.properties`:

```properties
storeFile=../../keystore/azmus-driver-release.jks
storePassword=***
keyAlias=azmus-driver
keyPassword=***
```

## 2. Build release APK

```powershell
cd driver-app
"VITE_API_URL=https://api.azmus.uz" | Out-File .env.production -Encoding utf8
npm ci
npm run build
npx cap sync android
cd android
.\gradlew.bat assembleRelease
```

Output:

```text
driver-app/android/app/build/outputs/apk/release/app-release.apk
```

Copy to distribution:

```text
deploy/AzmusERP-Production/apk/azmus-driver-1.0.0-release.apk
```

## 3. Publish for OTA (optional)

Upload APK to server:

```bash
scp app-release.apk azmus@VPS:/var/lib/azmus/data/uploads/mobile/azmus-driver-1.0.0.apk
```

Register version in ERP Settings → Mobile App.

## 4. Install on driver phones

- Distribute APK via Telegram / USB
- Server URL on login screen: `https://api.azmus.uz`
- Grant location **Allow all the time**
