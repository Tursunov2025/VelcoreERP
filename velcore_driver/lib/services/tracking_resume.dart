import 'package:background_locator_2/background_locator.dart';
import 'package:background_locator_2/settings/android_settings.dart';
import 'package:background_locator_2/settings/ios_settings.dart';
import 'package:background_locator_2/settings/locator_settings.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/constants.dart';
import 'location_callback_handler.dart';

/// Background locator ni qayta yoqish (telefon qayta yonganda / boot task).
class TrackingResume {
  static Future<bool> resumeIfNeeded() async {
    final prefs = await SharedPreferences.getInstance();
    final active = prefs.getBool(AppConstants.prefsTracking) ?? false;
    if (!active) return false;

    final vehicleId = prefs.getInt(AppConstants.prefsVehicleId);
    if (vehicleId == null) return false;

    if (await BackgroundLocator.isServiceRunning()) return true;

    await BackgroundLocator.initialize();
    await BackgroundLocator.registerLocationUpdate(
      callback: locationCallback,
      initCallback: locationInitCallback,
      disposeCallback: locationDisposeCallback,
      autoStop: false,
      androidSettings: AndroidSettings(
        accuracy: LocationAccuracy.NAVIGATION,
        interval: AppConstants.gpsUpdateIntervalSec,
        distanceFilter: 0,
        androidNotificationSettings: const AndroidNotificationSettings(
          notificationChannelName: 'Velcore GPS',
          notificationTitle: 'Velcore GPS faol',
          notificationMsg: 'Mashina kuzatilmoqda',
          notificationBigMsg: 'GPS har 5 soniyada serverga yuboriladi',
        ),
      ),
      iosSettings: const IOSSettings(
        accuracy: LocationAccuracy.NAVIGATION,
        distanceFilter: 0,
        showsBackgroundLocationIndicator: true,
      ),
    );
    return true;
  }
}

Future<void> markLastSignalTime() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(
    AppConstants.prefsLastSignalAt,
    DateTime.now().toUtc().toIso8601String(),
  );
}

Future<DateTime?> readLastSignalTime() async {
  final prefs = await SharedPreferences.getInstance();
  final raw = prefs.getString(AppConstants.prefsLastSignalAt);
  if (raw == null || raw.isEmpty) return null;
  return DateTime.tryParse(raw);
}
