import 'dart:async';
import 'dart:io';

import 'package:background_locator_2/background_locator.dart';
import 'package:background_locator_2/settings/android_settings.dart';
import 'package:background_locator_2/settings/ios_settings.dart';
import 'package:background_locator_2/settings/locator_settings.dart';
import 'package:battery_plus/battery_plus.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:workmanager/workmanager.dart';

import '../config/constants.dart';
import 'api_service.dart';
import 'location_callback_handler.dart';
import 'offline_queue_service.dart';
import 'storage_service.dart';
import 'tracking_resume.dart';

enum LocationPermissionStatus {
  granted,
  denied,
  deniedForever,
  serviceDisabled,
}

class TrackingService {
  TrackingService(this._storage, this._api, this._queue);

  final StorageService _storage;
  final ApiService _api;
  final OfflineQueueService _queue;

  StreamSubscription<Position>? _foregroundSub;
  StreamSubscription<BatteryState>? _batterySub;
  Timer? _foregroundTimer;
  final _battery = Battery();
  final _connectivity = Connectivity();
  int _batteryLevel = 0;

  bool get isActive => _storage.trackingActive;
  int get batteryLevel => _batteryLevel;

  /// Telefon qayta yonganda yoki ilova ochilganda tracking ni tiklash.
  Future<bool> resumeIfNeeded() async {
    if (!_storage.trackingActive) return false;
    await _ensureAndroid13Permissions();
    return TrackingResume.resumeIfNeeded();
  }

  Future<void> _ensureAndroid13Permissions() async {
    if (!Platform.isAndroid) return;
    final notif = await Permission.notification.status;
    if (notif.isDenied || notif.isLimited) {
      await Permission.notification.request();
    }
  }

  /// GPS ruxsati — rad etilsa Settings ga yo'naltirish uchun dialog.
  Future<LocationPermissionStatus> checkAndRequestPermissions(BuildContext context) async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      return LocationPermissionStatus.serviceDisabled;
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.deniedForever) {
      await _showOpenSettingsDialog(
        context,
        title: 'GPS ruxsati bloklangan',
        message: 'Kuzatuv uchun joylashuv ruxsatini Sozlamalar orqali yoqing.',
      );
      return LocationPermissionStatus.deniedForever;
    }

    if (permission == LocationPermission.denied) {
      return LocationPermissionStatus.denied;
    }

    if (Platform.isAndroid && permission == LocationPermission.whileInUse) {
      final bg = await Permission.locationAlways.status;
      if (!bg.isGranted) {
        final result = await Permission.locationAlways.request();
        if (!result.isGranted) {
          await _showOpenSettingsDialog(
            context,
            title: 'Doimiy GPS ruxsati kerak',
            message: 'Background kuzatuv uchun "Doim ruxsat berish" ni tanlang.',
          );
        }
      }
    }

    await _ensureAndroid13Permissions();
    return LocationPermissionStatus.granted;
  }

  Future<void> _showOpenSettingsDialog(
    BuildContext context, {
    required String title,
    required String message,
  }) async {
    if (!context.mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Bekor')),
          FilledButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await Geolocator.openAppSettings();
            },
            child: const Text('Sozlamalar'),
          ),
        ],
      ),
    );
  }

  Future<void> openLocationSettings() async {
    await Geolocator.openLocationSettings();
  }

  Future<bool> ensurePermissions(BuildContext context) async {
    final status = await checkAndRequestPermissions(context);
    if (status == LocationPermissionStatus.serviceDisabled) {
      if (context.mounted) {
        await _showOpenSettingsDialog(
          context,
          title: 'GPS o\'chiq',
          message: 'Telefon sozlamalarida joylashuv xizmatini yoqing.',
        );
        await Geolocator.openLocationSettings();
      }
      return false;
    }
    return status == LocationPermissionStatus.granted;
  }

  Future<void> startTracking({
    required int vehicleId,
    int? driverId,
    void Function(Position position, int sentCount, int battery)? onTick,
  }) async {
    await _storage.setVehicleId(vehicleId);
    if (driverId != null) await _storage.setDriverId(driverId);
    await _storage.setTrackingActive(true);
    await _ensureAndroid13Permissions();

    await Workmanager().registerOneOffTask(
      'velcore-boot-resume-active',
      AppConstants.workmanagerBootTask,
      existingWorkPolicy: ExistingWorkPolicy.replace,
      constraints: Constraints(networkType: NetworkType.not_required),
    );

    _batteryLevel = await _battery.batteryLevel;
    _batterySub?.cancel();
    _batterySub = _battery.onBatteryStateChanged.listen((_) async {
      _batteryLevel = await _battery.batteryLevel;
    });

    await BackgroundLocator.initialize();
    if (!await BackgroundLocator.isServiceRunning()) {
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
    }

    var sentCount = 0;
    await _sendCurrentPosition(onSent: () => sentCount++);

    _foregroundTimer?.cancel();
    _foregroundTimer = Timer.periodic(
      const Duration(seconds: AppConstants.gpsUpdateIntervalSec),
      (_) async {
        await _sendCurrentPosition(onSent: () => sentCount++);
      },
    );

    _foregroundSub?.cancel();
    _foregroundSub = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        distanceFilter: 5,
      ),
    ).listen((pos) {
      onTick?.call(pos, sentCount, _batteryLevel);
    });
  }

  Future<void> stopTracking() async {
    await _storage.setTrackingActive(false);
    _foregroundTimer?.cancel();
    _foregroundTimer = null;
    await _foregroundSub?.cancel();
    _foregroundSub = null;
    await _batterySub?.cancel();
    _batterySub = null;
    if (await BackgroundLocator.isServiceRunning()) {
      await BackgroundLocator.unRegisterLocationUpdate();
    }
  }

  Future<void> _sendCurrentPosition({void Function()? onSent}) async {
    if (!_storage.trackingActive) return;
    final vehicleId = _storage.vehicleId;
    if (vehicleId == null) return;

    Position? position;
    try {
      position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.bestForNavigation),
      );
    } catch (_) {
      return;
    }

    _batteryLevel = await _battery.batteryLevel;
    final connectivity = await _connectivity.checkConnectivity();
    final payload = <String, dynamic>{
      'vehicle_id': vehicleId,
      if (_storage.driverId != null) 'driver_id': _storage.driverId,
      'latitude': position.latitude,
      'longitude': position.longitude,
      'speed': position.speed >= 0 ? position.speed * 3.6 : 0,
      'battery_level': _batteryLevel.toDouble(),
      'signal_strength': _signalFromConnectivity(connectivity),
    };

    try {
      await _api.postGpsUpdate(payload);
      await _storage.setLastSignalAt(DateTime.now());
      onSent?.call();
    } catch (_) {
      await _queue.enqueue(payload);
    }
  }

  double _signalFromConnectivity(List<ConnectivityResult> results) {
    if (results.contains(ConnectivityResult.mobile)) return 3;
    if (results.contains(ConnectivityResult.wifi)) return 4;
    if (results.contains(ConnectivityResult.ethernet)) return 5;
    return 0;
  }
}
