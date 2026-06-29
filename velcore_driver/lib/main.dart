import 'package:flutter/material.dart';
import 'package:workmanager/workmanager.dart';

import 'app.dart';
import 'config/constants.dart';
import 'services/api_service.dart';
import 'services/crash_log_service.dart';
import 'services/offline_queue_service.dart';
import 'services/storage_service.dart';
import 'services/tracking_resume.dart';

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    try {
      if (task == AppConstants.workmanagerSyncTask) {
        final storage = await StorageService.create();
        final api = ApiService(storage);
        final queue = OfflineQueueService(storage, api);
        await queue.syncAll();
      } else if (task == AppConstants.workmanagerBootTask) {
        await TrackingResume.resumeIfNeeded();
      }
    } catch (e, st) {
      await CrashLogService.logError(e, st);
    }
    return Future.value(true);
  });
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await CrashLogService.init();

  await Workmanager().initialize(callbackDispatcher, isInDebugMode: false);
  await Workmanager().registerPeriodicTask(
    'velcore-gps-sync',
    AppConstants.workmanagerSyncTask,
    frequency: const Duration(minutes: 15),
    constraints: Constraints(networkType: NetworkType.connected),
  );
  await Workmanager().registerOneOffTask(
    'velcore-boot-resume',
    AppConstants.workmanagerBootTask,
    existingWorkPolicy: ExistingWorkPolicy.replace,
    constraints: Constraints(networkType: NetworkType.not_required),
  );

  final storage = await StorageService.create();
  if (storage.trackingActive) {
    await TrackingResume.resumeIfNeeded();
  }

  runApp(VelcoreDriverApp(storage: storage));
}
