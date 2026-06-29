import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

class CrashLogService {
  static const _fileName = 'velcore_driver_crash.log';
  static const _maxBytes = 512 * 1024;

  static Future<void> init() async {
    FlutterError.onError = (details) {
      FlutterError.presentError(details);
      unawaited(logError(details.exception, details.stack));
    };

    PlatformDispatcher.instance.onError = (error, stack) {
      unawaited(logError(error, stack));
      return true;
    };
  }

  static Future<File> _logFile() async {
    final dir = await getApplicationDocumentsDirectory();
    return File('${dir.path}/$_fileName');
  }

  static Future<void> logError(Object error, StackTrace? stack) async {
    try {
      final file = await _logFile();
      final entry = StringBuffer()
        ..writeln('--- ${DateTime.now().toIso8601String()} ---')
        ..writeln(error.toString());
      if (stack != null) {
        entry.writeln(stack.toString());
      }
      entry.writeln();

      if (await file.exists()) {
        final size = await file.length();
        if (size > _maxBytes) {
          final content = await file.readAsString();
          final trimmed = content.substring(content.length ~/ 2);
          await file.writeAsString(trimmed, flush: true);
        }
      }
      await file.writeAsString(entry.toString(), mode: FileMode.append, flush: true);
    } catch (_) {
      // Avoid recursive crash while logging
    }
  }

  static Future<String> readRecent({int maxLines = 80}) async {
    try {
      final file = await _logFile();
      if (!await file.exists()) return 'Crash log yo\'q.';
      final lines = await file.readAsLines();
      if (lines.isEmpty) return 'Crash log bo\'sh.';
      final tail = lines.length > maxLines ? lines.sublist(lines.length - maxLines) : lines;
      return tail.join('\n');
    } catch (e) {
      return 'Log o\'qib bo\'lmadi: $e';
    }
  }

  static Future<void> clear() async {
    final file = await _logFile();
    if (await file.exists()) {
      await file.delete();
    }
  }
}
