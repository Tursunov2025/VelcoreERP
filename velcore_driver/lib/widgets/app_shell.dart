import 'package:flutter/material.dart';



import 'pages/tasks_page.dart';

import 'pages/tracking_page.dart';

import 'pages/vehicle_select_page.dart';

import 'pages/settings_page.dart';

import '../services/api_service.dart';

import '../services/auth_service.dart';

import '../services/offline_queue_service.dart';

import '../services/storage_service.dart';

import '../services/tracking_service.dart';

import 'online_status_banner.dart';



class AppShell extends StatefulWidget {

  const AppShell({

    super.key,

    required this.storage,

    required this.api,

    required this.auth,

    required this.tracking,

    required this.queue,

    required this.onLogout,

  });



  final StorageService storage;

  final ApiService api;

  final AuthService auth;

  final TrackingService tracking;

  final OfflineQueueService queue;

  final VoidCallback onLogout;



  @override

  State<AppShell> createState() => _AppShellState();

}



class _AppShellState extends State<AppShell> {

  int _index = 0;

  bool _vehicleReady = false;



  @override

  void initState() {

    super.initState();

    _vehicleReady = widget.storage.vehicleId != null;

    _resumeTrackingAfterBoot();

  }



  Future<void> _resumeTrackingAfterBoot() async {

    if (!widget.storage.trackingActive) return;

    await widget.tracking.resumeIfNeeded();

  }



  void _onVehicleSelected() {

    setState(() {

      _vehicleReady = true;

      _index = 0;

    });

  }



  @override

  Widget build(BuildContext context) {

    if (!_vehicleReady) {

      return OnlineStatusBanner(

        child: VehicleSelectPage(

          api: widget.api,

          storage: widget.storage,

          onSelected: _onVehicleSelected,

        ),

      );

    }



    final pages = [

      TrackingPage(

        tracking: widget.tracking,

        storage: widget.storage,

        queue: widget.queue,

      ),

      TasksPage(api: widget.api),

      SettingsPage(

        storage: widget.storage,

        auth: widget.auth,

        tracking: widget.tracking,

        onLogout: widget.onLogout,

      ),

    ];



    return OnlineStatusBanner(

      child: Scaffold(

        body: IndexedStack(index: _index, children: pages),

        bottomNavigationBar: NavigationBar(

          selectedIndex: _index,

          onDestinationSelected: (i) => setState(() => _index = i),

          destinations: const [

            NavigationDestination(icon: Icon(Icons.gps_fixed), label: 'GPS'),

            NavigationDestination(icon: Icon(Icons.assignment), label: 'Vazifalar'),

            NavigationDestination(icon: Icon(Icons.settings), label: 'Sozlama'),

          ],

        ),

      ),

    );

  }

}

