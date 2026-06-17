# Azmus Driver — Android APK

Standalone driver app for continuous GPS tracking (`com.azmus.driver`).

## Features

- Login (JWT username/password)
- Vehicle & driver selection
- Start / Stop trip
- Foreground service GPS every 5 seconds (screen off)
- Offline queue + sync when online
- Status: vehicle, driver, last sent, GPS quality, battery

## Build APK

```powershell
cd driver-app
npm install
npm run apk:debug
```

Output:

```text
deploy/AzmusERP-Production/apk/azmus-driver-1.0.0-debug.apk
```

Set API URL before build:

```powershell
# .env or .env.production.local
VITE_API_URL=http://YOUR_LAN_IP:8000
# or Cloudflare tunnel API URL
VITE_API_URL=https://your-api.trycloudflare.com
```

Or edit server URL on the login screen after install.

## Install on phone

1. Copy `azmus-driver-1.0.0-debug.apk` to the phone (USB, Telegram, etc.)
2. Enable **Install unknown apps** for your file manager
3. Open the APK and tap Install
4. Grant **Location** → **Allow all the time** (required for background tracking)
5. Grant **Notifications** (foreground service indicator)

## First run

1. Open **Azmus Driver**
2. Enter server URL (same backend as ERP, e.g. `http://192.168.1.110:8000`)
3. Sign in with ERP username/password
4. Select vehicle → **Start Trip**
5. Dispatchers see live position on `/transport/live-map`

## Permissions (Android)

- Fine location + background location
- Foreground service (location type)
- Internet

## Stop tracking

Tap **Stop Trip** before uninstalling or signing out.
