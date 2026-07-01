import 'dart:convert';

import 'package:battery_plus/battery_plus.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:background_locator_2/location_dto.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/constants.dart';

@pragma('vm:entry-point')
void locationCallback(LocationDto data) {
  LocationCallbackHandler.handle(data);
}

@pragma('vm:entry-point')
void locationInitCallback(Map<String, dynamic> params) {}

@pragma('vm:entry-point')
void locationDisposeCallback() {}

class LocationCallbackHandler {
  static Future<void> handle(LocationDto data) async {
    final prefs = await SharedPreferences.getInstance();
    final tracking = prefs.getBool(AppConstants.prefsTracking) ?? false;
    if (!tracking) return;

    final vehicleId = prefs.getInt(AppConstants.prefsVehicleId);
    if (vehicleId == null) return;

    final driverId = prefs.getInt(AppConstants.prefsDriverId);
    final apiUrl = prefs.getString(AppConstants.prefsApiUrl) ?? AppConstants.defaultApiUrl;
    final accessToken = _readAccessToken(prefs);
    if (accessToken == null) return;

    final batteryLevel = await Battery().batteryLevel;
    final connectivity = await Connectivity().checkConnectivity();
    final speedMs = data.speed;
    final payload = <String, dynamic>{
      'vehicle_id': vehicleId,
      if (driverId != null) 'driver_id': driverId,
      'latitude': data.latitude,
      'longitude': data.longitude,
      'speed': speedMs >= 0 ? speedMs * 3.6 : 0,
      'battery_level': batteryLevel.toDouble(),
      'signal_strength': _signalFromConnectivity(connectivity),
    };

    try {
      final dio = Dio(
        BaseOptions(
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 15),
          headers: {
            'Authorization': 'Bearer $accessToken',
            'Content-Type': 'application/json',
          },
        ),
      );
      await dio.post('$apiUrl/gps/update', data: payload);
      await prefs.setString(
        AppConstants.prefsLastSignalAt,
        DateTime.now().toUtc().toIso8601String(),
      );
    } catch (_) {
      await _enqueue(prefs, payload);
    }
  }

  static String? _readAccessToken(SharedPreferences prefs) {
    final raw = prefs.getString(AppConstants.prefsTokens);
    if (raw == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      return map['access_token'] as String?;
    } catch (_) {
      return null;
    }
  }

  static double _signalFromConnectivity(List<ConnectivityResult> results) {
    if (results.contains(ConnectivityResult.mobile)) return 3;
    if (results.contains(ConnectivityResult.wifi)) return 4;
    if (results.contains(ConnectivityResult.ethernet)) return 5;
    return 0;
  }

  static Future<void> _enqueue(SharedPreferences prefs, Map<String, dynamic> payload) async {
    final raw = prefs.getString(AppConstants.prefsOfflineQueue);
    final queue = <Map<String, dynamic>>[];
    if (raw != null && raw.isNotEmpty) {
      try {
        final list = jsonDecode(raw) as List<dynamic>;
        for (final item in list) {
          queue.add(Map<String, dynamic>.from(item as Map));
        }
      } catch (_) {}
    }
    queue.add(payload);
    while (queue.length > AppConstants.offlineQueueMax) {
      queue.removeAt(0);
    }
    await prefs.setString(AppConstants.prefsOfflineQueue, jsonEncode(queue));
  }
}
