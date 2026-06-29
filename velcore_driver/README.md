# Velcore Driver — Flutter Android APK

Haydovchi GPS ilovasi: telefon login, mashina tanlash, background GPS (5s), offline navbat, Google Maps navigatsiya.

## Talablar

- [Flutter SDK](https://docs.flutter.dev/get-started/install) 3.22+
- Android SDK (API 34)
- JDK 17

## Birinchi sozlash

```powershell
cd velcore_driver

# Gradle wrapper va icon fayllar uchun (birinchi marta):
flutter create --org uz.velcore --project-name velcore_driver .

flutter pub get
```

---

## APK yig'ish — Release (production)

Production telefonlar uchun **Release APK** ishlating.

```powershell
cd velcore_driver
flutter pub get
flutter build apk --release
```

**Chiqish fayl:**

```text
build/app/outputs/flutter-apk/app-release.apk
```

**Nusxa olish (ixtiyoriy):**

```powershell
Copy-Item build/app/outputs/flutter-apk/app-release.apk `
  ../deploy/AzmusERP-Production/apk/velcore-driver-1.0.0-release.apk
```

Release APK xususiyatlari:
- Optimizatsiya qilingan (kichikroq hajm)
- Debug banner yo'q
- Production API: `https://api.velcore.uz`

---

## APK yig'ish — Debug (test)

Ichki test va USB orqali `flutter run` uchun **Debug APK**.

```powershell
cd velcore_driver
flutter pub get
flutter build apk --debug
```

**Chiqish fayl:**

```text
build/app/outputs/flutter-apk/app-debug.apk
```

Debug APK xususiyatlari:
- Tezroq yig'iladi
- Hot reload / devtools bilan ishlaydi
- Hajmi kattaroq

---

## Skript orqali ikkala APK

```powershell
cd velcore_driver
.\scripts\build_apk.ps1
```

Chiqish:
- `deploy/AzmusERP-Production/apk/velcore-driver-1.0.0-release.apk`
- `deploy/AzmusERP-Production/apk/velcore-driver-1.0.0-debug.apk`

---

## Telefonga o'rnatish

```powershell
# USB ulangan qurilma
flutter install --release

# yoki adb
adb install -r build/app/outputs/flutter-apk/app-release.apk
```

---

## Backend API

Default: `https://api.velcore.uz`

| Endpoint | Vazifa |
|----------|--------|
| `POST /auth/login-by-phone` | Telefon + parol |
| `GET /gps/vehicles` | Mashinalar |
| `GET /gps/tasks` | Vazifalar |
| `POST /gps/update` | GPS (5s) — batareya, tezlik, signal |
| `POST /gps/tasks/{id}/stop` | Marshrut "Bajarildi" |

**Login:** ERP da `username` = telefon raqami (`998901234567`).

---

## Yangi funksiyalar (v1.0)

| # | Funksiya |
|---|----------|
| 1 | **Online/Offline** — yuqori banner (barcha sahifalar) |
| 2 | **Batareya %** — UI + `battery_level` serverga |
| 3 | **Oxirgi signal vaqti** — muvaffaqiyatli POST dan keyin |
| 4 | **Boot resume** — telefon qayta yonganda tracking tiklanadi |
| 5 | **Android 13+** — `POST_NOTIFICATIONS`, foreground service location |
| 6 | **GPS ruxsati** — rad etilsa Sozlamalar dialogi |
| 7 | **Google Maps** — vazifalar sahifasida navigatsiya |
| 8 | **Bajarildi** — faol vazifani yopish |
| 9 | **Crash log** — Sozlamalar → Crash loglar |
| 10 | **Release/Debug** — yuqoridagi yo'riqnoma |

---

## Android ruxsatlar (o'rnatgach)

1. **Joylashuv** → **Doim ruxsat berish**
2. **Bildirishnomalar** — Android 13+ foreground xizmat uchun
3. Google Maps o'rnatilgan bo'lishi kerak (navigatsiya uchun)

---

## Paketlar

- `geolocator`, `background_locator_2`, `workmanager`, `dio`, `shared_preferences`
- `battery_plus`, `connectivity_plus`, `url_launcher`, `path_provider`, `permission_handler`

---

## VPS

```bash
cd /var/www/velcore && git pull && sudo systemctl restart velcore.service
```
