import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../config/constants.dart';
import '../services/auth_service.dart';
import '../services/crash_log_service.dart';
import '../services/storage_service.dart';
import '../services/tracking_service.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({
    super.key,
    required this.storage,
    required this.auth,
    required this.tracking,
    required this.onLogout,
  });

  final StorageService storage;
  final AuthService auth;
  final TrackingService tracking;
  final VoidCallback onLogout;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late final TextEditingController _apiCtrl;

  @override
  void initState() {
    super.initState();
    _apiCtrl = TextEditingController(text: widget.storage.apiUrl);
  }

  @override
  void dispose() {
    _apiCtrl.dispose();
    super.dispose();
  }

  Future<void> _saveApi() async {
    await widget.storage.setApiUrl(_apiCtrl.text.trim());
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('API URL saqlandi')));
  }

  Future<void> _logout() async {
    if (widget.tracking.isActive) {
      await widget.tracking.stopTracking();
    }
    await widget.auth.logout();
    widget.onLogout();
  }

  Future<void> _showCrashLogs() async {
    final text = await CrashLogService.readRecent();
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Crash loglar'),
        content: SingleChildScrollView(child: Text(text, style: const TextStyle(fontSize: 12))),
        actions: [
          TextButton(
            onPressed: () async {
              await CrashLogService.clear();
              if (ctx.mounted) Navigator.pop(ctx);
            },
            child: const Text('Tozalash'),
          ),
          FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('Yopish')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final session = widget.auth.session;
    return Scaffold(
      appBar: AppBar(title: const Text('Sozlamalar')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.person),
              title: Text(session?.username ?? '—'),
              subtitle: Text('Rol: ${session?.role ?? "—"}'),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _apiCtrl,
            decoration: const InputDecoration(
              labelText: 'Backend URL',
              hintText: AppConstants.defaultApiUrl,
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.cloud),
            ),
          ),
          const SizedBox(height: 8),
          FilledButton(onPressed: _saveApi, child: const Text('API URL saqlash')),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () => Geolocator.openAppSettings(),
            icon: const Icon(Icons.location_on),
            label: const Text('GPS ruxsatlari (Sozlamalar)'),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _showCrashLogs,
            icon: const Icon(Icons.bug_report_outlined),
            label: const Text('Crash loglar'),
          ),
          const SizedBox(height: 24),
          const ListTile(
            leading: Icon(Icons.info_outline),
            title: Text('Versiya'),
            subtitle: Text('1.0.0 · Velcore Driver'),
          ),
          const SizedBox(height: 24),
          OutlinedButton.icon(
            onPressed: _logout,
            icon: const Icon(Icons.logout, color: Colors.red),
            label: const Text('Chiqish', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}
