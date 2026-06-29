import 'package:flutter/material.dart';

import '../models/transport_task.dart';
import '../services/api_service.dart';
import '../utils/maps_launcher.dart';

class TasksPage extends StatefulWidget {
  const TasksPage({super.key, required this.api});

  final ApiService api;

  @override
  State<TasksPage> createState() => _TasksPageState();
}

class _TasksPageState extends State<TasksPage> {
  List<TransportTask> _tasks = [];
  bool _loading = true;
  String? _error;
  String _filter = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final tasks = await widget.api.fetchTasks(status: _filter);
      setState(() {
        _tasks = tasks;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _startTask(TransportTask task) async {
    try {
      await widget.api.startTask(task.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${task.title} boshlandi')));
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _completeTask(TransportTask task) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Marshrutni yopish'),
        content: Text('"${task.title}" bajarildi deb belgilansinmi?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Bekor')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Bajarildi')),
        ],
      ),
    );
    if (ok != true) return;

    try {
      await widget.api.completeTask(task.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${task.title} — bajarildi')),
      );
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _openMaps(TransportTask task) async {
    final dest = task.destination.trim().isNotEmpty ? task.destination : task.origin;
    if (dest.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Manzil koordinatasi yoki manzil matni yo\'q')),
      );
      return;
    }
    final launched = await MapsLauncher.openNavigation(destinationAddress: dest);
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Google Maps ochilmadi')),
      );
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'active':
        return Colors.green;
      case 'completed':
        return Colors.blueGrey;
      case 'cancelled':
        return Colors.red;
      default:
        return Colors.orange;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Vazifalar'),
        actions: [
          PopupMenuButton<String>(
            onSelected: (v) {
              setState(() => _filter = v);
              _load();
            },
            itemBuilder: (context) => const [
              PopupMenuItem(value: '', child: Text('Barchasi')),
              PopupMenuItem(value: 'assigned', child: Text('Tayinlangan')),
              PopupMenuItem(value: 'active', child: Text('Faol')),
              PopupMenuItem(value: 'completed', child: Text('Yakunlangan')),
            ],
            icon: const Icon(Icons.filter_list),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
                  if (_tasks.isEmpty && _error == null)
                    const Padding(
                      padding: EdgeInsets.all(32),
                      child: Center(child: Text('Vazifalar yo\'q')),
                    ),
                  ..._tasks.map((t) => Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(t.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                              if (t.origin.isNotEmpty || t.destination.isNotEmpty)
                                Padding(
                                  padding: const EdgeInsets.only(top: 4),
                                  child: Text('${t.origin} → ${t.destination}'),
                                ),
                              if (t.vehiclePlate != null) Text('Mashina: ${t.vehiclePlate}'),
                              const SizedBox(height: 8),
                              Chip(
                                label: Text(t.status),
                                backgroundColor: _statusColor(t.status).withOpacity(0.15),
                                labelStyle: TextStyle(color: _statusColor(t.status)),
                                visualDensity: VisualDensity.compact,
                              ),
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: [
                                  if (t.destination.isNotEmpty || t.origin.isNotEmpty)
                                    OutlinedButton.icon(
                                      onPressed: () => _openMaps(t),
                                      icon: const Icon(Icons.map, size: 18),
                                      label: const Text('Google Maps'),
                                    ),
                                  if (t.status == 'assigned')
                                    FilledButton.icon(
                                      onPressed: () => _startTask(t),
                                      icon: const Icon(Icons.play_arrow, size: 18),
                                      label: const Text('Boshlash'),
                                    ),
                                  if (t.status == 'active')
                                    FilledButton.icon(
                                      onPressed: () => _completeTask(t),
                                      icon: const Icon(Icons.check_circle, size: 18),
                                      label: const Text('Bajarildi'),
                                      style: FilledButton.styleFrom(backgroundColor: Colors.green),
                                    ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      )),
                ],
              ),
            ),
    );
  }
}
