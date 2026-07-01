# Velcore Driver V1 — Flutter Android APK

Haydovchi mobil ilova: telefon + parol login, background GPS (5s), chat, foto, Yandex Navigator.

## V1 funksiyalar

| # | Funksiya |
|---|----------|
| 1 | Telefon + parol login (`POST /driver/login`) |
| 2 | Android background GPS (`background_locator_2`) |
| 3 | GPS har **5 soniyada** (`POST /gps/update`) |
| 4 | Ilova yopiq / telefon qayta yonganda ham ishlaydi (`workmanager` + boot resume) |
| 5 | Chat moduli (`GET/POST /driver/messages`) |
| 6 | Foto yuborish (`POST /driver/photo`) |
| 7 | Yandex Navigator integratsiyasi |
| 8 | 3 ichki + 5 tashqi fura haydovchisi (`driver_type`: internal/external) |
| 9 | Vazifalar (`GET /driver/tasks`) |

## Haydovchilar (seed)

| Tur | Telefon (username) | Parol (ERP User yaratish kerak) |
|-----|-------------------|--------------------------------|
| Ichki 1–3 | 998901111101 … 103 | admin tomonidan |
| Tashqi 1–5 | 998902222201 … 205 | admin tomonidan |

ERP da **User** yaratish: `username` = telefon raqami, `department` = `Logistika`, parol o'rnatish.

## APK yig'ish — Release

```powershell
cd velcore_driver
.\scripts\build_apk.ps1
```

Chiqish:
- `build/app/outputs/flutter-apk/app-release.apk`
- `deploy/AzmusERP-Production/apk/velcore-driver-1.0.0-release.apk`

## Backend API

| Endpoint | Vazifa |
|----------|--------|
| `POST /driver/login` | Telefon + parol, driver + vehicle profil |
| `GET /driver/tasks` | Haydovchi vazifalari |
| `POST /driver/tasks/{id}/start` | Vazifani boshlash |
| `POST /driver/tasks/{id}/complete` | Vazifani yopish |
| `GET /driver/messages` | Chat xabarlari |
| `POST /driver/messages` | Matn yuborish |
| `POST /driver/photo` | Foto yuklash + chat |
| `POST /gps/update` | GPS ping (5s) |

Default API: `https://api.velcore.uz`

## Android ruxsatlar

1. Joylashuv → **Doim ruxsat berish**
2. Bildirishnomalar (Android 13+)
3. Kamera / galereya (foto uchun)
4. Yandex Navigator o'rnatilgan bo'lishi kerak

## VPS deploy

```bash
cd /var/www/velcore && git pull && sudo systemctl restart velcore.service
```
