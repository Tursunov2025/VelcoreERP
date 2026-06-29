import '../config/constants.dart';
import 'api_service.dart';
import 'storage_service.dart';

class OfflineQueueService {
  OfflineQueueService(this._storage, this._api);

  final StorageService _storage;
  final ApiService _api;

  Future<int> enqueue(Map<String, dynamic> payload) async {
    final queue = _storage.offlineQueue;
    queue.add(payload);
    while (queue.length > AppConstants.offlineQueueMax) {
      queue.removeAt(0);
    }
    await _storage.setOfflineQueue(queue);
    return queue.length;
  }

  Future<({int synced, int remaining})> syncAll() async {
    final queue = _storage.offlineQueue;
    if (queue.isEmpty) return (synced: 0, remaining: 0);

    final remaining = <Map<String, dynamic>>[];
    var synced = 0;
    for (final item in queue) {
      try {
        await _api.postGpsUpdate(item);
        await _storage.setLastSignalAt(DateTime.now());
        synced++;
      } catch (_) {
        remaining.add(item);
      }
    }
    await _storage.setOfflineQueue(remaining);
    return (synced: synced, remaining: remaining.length);
  }

  int get pendingCount => _storage.offlineQueue.length;
}
