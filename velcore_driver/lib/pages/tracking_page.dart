import 'dart:async';

import 'package:battery_plus/battery_plus.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:intl/intl.dart';

import '../services/offline_queue_service.dart';
import '../services/storage_service.dart';
import '../services/tracking_service.dart';

class TrackingPage extends StatefulWidget {
  const TrackingPage({
    super.key,
    required this.tracking,
    required this.storage,
    required this.queue,
  });

  final TrackingService tracking;
  final StorageService storage;
  final OfflineQueueService queue;

  @override
  State<TrackingPage> createState() => _TrackingPageState();
}

class _TrackingPageState extends State<TrackingPage> {
  bool _tracking = false;
  bool _busy = false;
  Position? _position;
  int _sentCount = 0;
  int _pending = 0;
  bool _online = true;
  int _battery = 0;
  DateTime? _lastSignal;
  String? _error;
  Timer? _uiTimer;
  final _battery = Battery();

  @override
  void initState() {
    super.initState();
    _tracking = widget.storage.trackingActive;
    _pending = widget.queue.pendingCount;
    _lastSignal = widget.storage.lastSignalAt;
    _listenConnectivity();
    _loadBattery();
    if (_tracking) {
      _resumeUi();
      unawaited(widget.tracking.resumeIfNeeded());
    }
    _uiTimer = Timer.periodic(const Duration(seconds: 2), (_) => _refreshMeta());
  }

  Future<void> _refreshMeta() async {
    if (!mounted) return;
    setState(() {
      _lastSignal = widget.storage.lastSignalAt;
      _pending = widget.queue.pendingCount;
    });
  }

  Future<void> _loadBattery() async {
    try {
      final level = await _battery.batteryLevel;
      if (mounted) setState(() => _battery = level);
    } catch (_) {}
  }

  void _listenConnectivity() {
    Connectivity().checkConnectivity().then((r) {
      if (mounted) setState(() => _online = !r.contains(ConnectivityResult.none));
    });
    Connectivity().onConnectivityChanged.listen((results) async {
      final online = !results.contains(ConnectivityResult.none);
      if (mounted) setState(() => _online = online);
      if (online) await _syncQueue();
    });
  }

  Future<void> _syncQueue() async {
    final result = await widget.queue.syncAll();
    if (!mounted) return;
    setState(() {
      _pending = result.remaining;
      _sentCount += result.synced;
      _lastSignal = widget.storage.lastSignalAt;
    });
  }

  Future<void> _resumeUi() async {
    try {
      final pos = await Geolocator.getCurrentPosition();
      if (mounted) setState(() => _position = pos);
    } catch (_) {}
  }

  Future<void> _start() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final vehicleId = widget.storage.vehicleId;
    if (vehicleId == null) {
      setState(() {
        _error = 'Avval mashina tanlang';
        _busy = false;
      });
      return;
    }

    final ok = await widget.tracking.ensurePermissions(context);
    if (!ok) {
      setState(() {
        _error = 'GPS ruxsati kerak — Sozlamalarni oching';
        _busy = false;
      });
      return;
    }

    try {
      await widget.tracking.startTracking(
        vehicleId: vehicleId,
        driverId: widget.storage.driverId,
        onTick: (pos, sent, battery) {
          if (!mounted) return;
          setState(() {
            _position = pos;
            _sentCount = sent;
            _battery = battery;
            _lastSignal = widget.storage.lastSignalAt ?? DateTime.now();
          });
        },
      );
      if (!mounted) return;
      setState(() {
        _tracking = true;
        _busy = false;
        _lastSignal = DateTime.now();
        _sentCount = 1;
      });
      await _loadBattery();
    } catch (e) {
      setState(() {
        _error = e.toString();
        _busy = false;
      });
    }
  }

  Future<void> _stop() async {
    setState(() => _busy = true);
    await widget.tracking.stopTracking();
    if (!mounted) return;
    setState(() {
      _tracking = false;
      _busy = false;
    });
  }

  @override
  void dispose() {
    _uiTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fmt = DateFormat('dd.MM.yyyy HH:mm:ss');
    return Scaffold(
      appBar: AppBar(title: const Text('GPS kuzatuv')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              _StatCard(
                label: 'Kuzatuv',
                value: _tracking ? 'Live' : 'O\'chiq',
                color: _tracking ? Colors.green : Colors.grey,
                icon: Icons.gps_fixed,
              ),
              const SizedBox(width: 12),
              _StatCard(
                label: 'Server',
                value: _online ? 'Online' : 'Offline',
                color: _online ? Colors.blue : Colors.orange,
                icon: _online ? Icons.wifi : Icons.wifi_off,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _StatCard(
                label: 'Batareya',
                value: '$_battery%',
                color: _battery > 20 ? Colors.teal : Colors.red,
                icon: Icons.battery_std,
              ),
              const SizedBox(width: 12),
              _StatCard(
                label: 'Navbat',
                value: '$_pending',
                color: Colors.deepOrange,
                icon: Icons.cloud_queue,
              ),
            ],
          ),
          const SizedBox(height: 24),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Mashina ID: ${widget.storage.vehicleId ?? "—"}'),
                  Text('Haydovchi ID: ${widget.storage.driverId ?? "—"}'),
                  const SizedBox(height: 8),
                  if (_position != null)
                    Text(
                      '📍 ${_position!.latitude.toStringAsFixed(5)}, ${_position!.longitude.toStringAsFixed(5)}'
                      '${_position!.accuracy > 0 ? " (±${_position!.accuracy.toStringAsFixed(0)}m)" : ""}',
                    ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      const Icon(Icons.access_time, size: 16, color: Colors.grey),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          _lastSignal != null
                              ? 'Oxirgi signal: ${fmt.format(_lastSignal!.toLocal())}'
                              : 'Oxirgi signal: hali yuborilmagan',
                          style: const TextStyle(color: Colors.grey),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text('Yuborilgan ping: $_sentCount', style: const TextStyle(fontSize: 12, color: Colors.grey)),
                  const SizedBox(height: 8),
                  const Text(
                    'Batareya %, tezlik va signal kuchi POST /gps/update bilan yuboriladi. '
                    'Qulf ekranda background xizmat ishlaydi.',
                    style: TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                ],
              ),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
          const SizedBox(height: 24),
          if (!_tracking)
            FilledButton.icon(
              onPressed: _busy ? null : _start,
              icon: const Icon(Icons.play_arrow_rounded),
              label: Text(_busy ? 'Boshlanmoqda…' : 'Start Tracking'),
              style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 18)),
            )
          else
            FilledButton.icon(
              onPressed: _busy ? null : _stop,
              icon: const Icon(Icons.stop_rounded),
              label: const Text('To\'xtatish'),
              style: FilledButton.styleFrom(
                backgroundColor: Colors.red,
                padding: const EdgeInsets.symmetric(vertical: 18),
              ),
            ),
          if (_pending > 0) ...[
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: _syncQueue,
              child: Text('Navbatni yuborish ($_pending)'),
            ),
          ],
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.label,
    required this.value,
    required this.color,
    required this.icon,
  });

  final String label;
  final String value;
  final Color color;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(icon, size: 14, color: color),
                  const SizedBox(width: 4),
                  Text(label.toUpperCase(), style: const TextStyle(fontSize: 11, color: Colors.grey)),
                ],
              ),
              const SizedBox(height: 4),
              Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: color)),
            ],
          ),
        ),
      ),
    );
  }
}
