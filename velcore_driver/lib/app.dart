import 'package:flutter/material.dart';



import 'services/api_service.dart';

import 'services/auth_service.dart';

import 'services/offline_queue_service.dart';

import 'services/storage_service.dart';

import 'services/tracking_service.dart';

import 'pages/login_page.dart';

import 'widgets/app_shell.dart';



class VelcoreDriverApp extends StatefulWidget {

  const VelcoreDriverApp({super.key, required this.storage});



  final StorageService storage;



  @override

  State<VelcoreDriverApp> createState() => _VelcoreDriverAppState();

}



class _VelcoreDriverAppState extends State<VelcoreDriverApp> {

  late final ApiService _api;

  late final AuthService _auth;

  late final OfflineQueueService _queue;

  late final TrackingService _tracking;



  @override

  void initState() {

    super.initState();

    _api = ApiService(widget.storage);

    _auth = AuthService(widget.storage, _api);

    _queue = OfflineQueueService(widget.storage, _api);

    _tracking = TrackingService(widget.storage, _api, _queue);

  }



  @override

  Widget build(BuildContext context) {

    return MaterialApp(

      title: 'Velcore Driver',

      debugShowCheckedModeBanner: false,

      theme: ThemeData(

        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1E3A8A)),

        useMaterial3: true,

      ),

      home: _auth.isLoggedIn

          ? AppShell(

              storage: widget.storage,

              api: _api,

              auth: _auth,

              tracking: _tracking,

              queue: _queue,

              onLogout: () => setState(() {}),

            )

          : LoginPage(

              auth: _auth,

              onLoggedIn: () => setState(() {}),

            ),

    );

  }

}

