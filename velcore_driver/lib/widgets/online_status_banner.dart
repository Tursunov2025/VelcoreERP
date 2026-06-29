import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';

/// Global Online/Offline holat banneri.
class OnlineStatusBanner extends StatefulWidget {
  const OnlineStatusBanner({super.key, required this.child});

  final Widget child;

  @override
  State<OnlineStatusBanner> createState() => _OnlineStatusBannerState();
}

class _OnlineStatusBannerState extends State<OnlineStatusBanner> {
  bool _online = true;
  StreamSubscription<List<ConnectivityResult>>? _sub;

  @override
  void initState() {
    super.initState();
    _check();
    _sub = Connectivity().onConnectivityChanged.listen((results) {
      if (!mounted) return;
      setState(() => _online = _isOnline(results));
    });
  }

  bool _isOnline(List<ConnectivityResult> results) {
    return !results.contains(ConnectivityResult.none) && results.isNotEmpty;
  }

  Future<void> _check() async {
    final results = await Connectivity().checkConnectivity();
    if (mounted) setState(() => _online = _isOnline(results));
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          width: double.infinity,
          color: _online ? const Color(0xFF166534) : const Color(0xFFB45309),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              Icon(_online ? Icons.cloud_done : Icons.cloud_off, color: Colors.white, size: 18),
              const SizedBox(width: 8),
              Text(
                _online ? 'Online — serverga ulanish mavjud' : 'Offline — GPS navbatga saqlanadi',
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 13),
              ),
            ],
          ),
        ),
        Expanded(child: widget.child),
      ],
    );
  }
}
