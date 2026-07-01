import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../config/constants.dart';
import '../models/auth_session.dart';

class StorageService {
  StorageService(this._prefs);

  final SharedPreferences _prefs;

  static Future<StorageService> create() async {
    return StorageService(await SharedPreferences.getInstance());
  }

  String get apiUrl =>
      _prefs.getString(AppConstants.prefsApiUrl) ?? AppConstants.defaultApiUrl;

  Future<void> setApiUrl(String url) async {
    await _prefs.setString(AppConstants.prefsApiUrl, url.replaceAll(RegExp(r'/+$'), ''));
  }

  AuthSession? get session {
    final raw = _prefs.getString(AppConstants.prefsTokens);
    if (raw == null || raw.isEmpty) return null;
    try {
      return AuthSession.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }

  Future<void> setSession(AuthSession? session) async {
    if (session == null) {
      await _prefs.remove(AppConstants.prefsTokens);
      return;
    }
    await _prefs.setString(AppConstants.prefsTokens, jsonEncode(session.toJson()));
  }

  int? get driverId => _prefs.getInt(AppConstants.prefsDriverId);

  Future<void> setDriverId(int? id) async {
    if (id == null) {
      await _prefs.remove(AppConstants.prefsDriverId);
    } else {
      await _prefs.setInt(AppConstants.prefsDriverId, id);
    }
  }

  String get driverPhone => _prefs.getString(AppConstants.prefsDriverPhone) ?? '';

  Future<void> setDriverPhone(String phone) async {
    await _prefs.setString(AppConstants.prefsDriverPhone, phone);
  }

  String get driverType => _prefs.getString(AppConstants.prefsDriverType) ?? '';

  Future<void> setDriverType(String type) async {
    if (type.isEmpty) {
      await _prefs.remove(AppConstants.prefsDriverType);
    } else {
      await _prefs.setString(AppConstants.prefsDriverType, type);
    }
  }

  int? get vehicleId => _prefs.getInt(AppConstants.prefsVehicleId);

  Future<void> setVehicleId(int? id) async {
    if (id == null) {
      await _prefs.remove(AppConstants.prefsVehicleId);
    } else {
      await _prefs.setInt(AppConstants.prefsVehicleId, id);
    }
  }

  bool get trackingActive => _prefs.getBool(AppConstants.prefsTracking) ?? false;

  Future<void> setTrackingActive(bool value) async {
    await _prefs.setBool(AppConstants.prefsTracking, value);
  }

  List<Map<String, dynamic>> get offlineQueue {
    final raw = _prefs.getString(AppConstants.prefsOfflineQueue);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> setOfflineQueue(List<Map<String, dynamic>> queue) async {
    await _prefs.setString(AppConstants.prefsOfflineQueue, jsonEncode(queue));
  }

  DateTime? get lastSignalAt {
    final raw = _prefs.getString(AppConstants.prefsLastSignalAt);
    if (raw == null || raw.isEmpty) return null;
    return DateTime.tryParse(raw);
  }

  Future<void> setLastSignalAt(DateTime? time) async {
    if (time == null) {
      await _prefs.remove(AppConstants.prefsLastSignalAt);
    } else {
      await _prefs.setString(AppConstants.prefsLastSignalAt, time.toUtc().toIso8601String());
    }
  }
}
