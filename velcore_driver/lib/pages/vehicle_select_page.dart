import 'package:flutter/material.dart';

import '../models/vehicle.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

class VehicleSelectPage extends StatefulWidget {
  const VehicleSelectPage({
    super.key,
    required this.api,
    required this.storage,
    required this.onSelected,
  });

  final ApiService api;
  final StorageService storage;
  final VoidCallback onSelected;

  @override
  State<VehicleSelectPage> createState() => _VehicleSelectPageState();
}

class _VehicleSelectPageState extends State<VehicleSelectPage> {
  List<Vehicle> _vehicles = [];
  bool _loading = true;
  String? _error;
  int? _selectedId;

  @override
  void initState() {
    super.initState();
    _selectedId = widget.storage.vehicleId;
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final vehicles = await widget.api.fetchVehicles();
      setState(() {
        _vehicles = vehicles.where((v) => v.status == 'active').toList();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _save() async {
    if (_selectedId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Mashina tanlang')),
      );
      return;
    }
    await widget.storage.setVehicleId(_selectedId);
    widget.onSelected();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mashina tanlash')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    'O\'z mashinangizni tanlang',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Tanlangan mashina GPS kuzatuvda ishlatiladi.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!, style: const TextStyle(color: Colors.red)),
                  ],
                  const SizedBox(height: 16),
                  ..._vehicles.map(
                    (v) => Card(
                      child: RadioListTile<int>(
                        value: v.id,
                        groupValue: _selectedId,
                        onChanged: (id) => setState(() => _selectedId = id),
                        title: Text(v.plateNumber, style: const TextStyle(fontWeight: FontWeight.bold)),
                        subtitle: Text(v.model.isEmpty ? v.status : v.model),
                        secondary: const Icon(Icons.directions_car_filled),
                      ),
                    ),
                  ),
                  if (_vehicles.isEmpty && !_loading)
                    const Padding(
                      padding: EdgeInsets.all(24),
                      child: Text('Faol mashinalar topilmadi. Admin paneldan qo\'shing.'),
                    ),
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: _save,
                    style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16)),
                    child: const Text('Davom etish'),
                  ),
                ],
              ),
            ),
    );
  }
}
