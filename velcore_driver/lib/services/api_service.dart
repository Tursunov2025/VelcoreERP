import 'package:dio/dio.dart';

import '../models/auth_session.dart';
import '../models/chat_message.dart';
import '../models/driver.dart';
import '../models/transport_task.dart';
import '../models/vehicle.dart';
import 'storage_service.dart';

class ApiService {
  ApiService(this._storage);

  final StorageService _storage;
  late final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 20),
      receiveTimeout: const Duration(seconds: 20),
      headers: {'Content-Type': 'application/json'},
    ),
  );

  String get baseUrl => _storage.apiUrl;

  Future<Response<dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? data,
    Map<String, dynamic>? query,
    bool retry = true,
  }) async {
    final session = _storage.session;
    final options = Options(method: method);
    if (session != null) {
      options.headers = {'Authorization': 'Bearer ${session.accessToken}'};
    }
    try {
      return await _dio.request(
        '${_storage.apiUrl}$path',
        data: data,
        queryParameters: query,
        options: options,
      );
    } on DioException catch (e) {
      if (e.response?.statusCode == 401 && retry && session != null) {
        final refreshed = await refreshToken();
        if (refreshed) {
          return _request(method, path, data: data, query: query, retry: false);
        }
      }
      final detail = e.response?.data;
      var message = e.message ?? 'Network error';
      if (detail is Map && detail['detail'] != null) {
        message = detail['detail'].toString();
      }
      throw ApiException(message, statusCode: e.response?.statusCode);
    }
  }

  Future<bool> refreshToken() async {
    final session = _storage.session;
    if (session == null) return false;
    try {
      final res = await _dio.post(
        '${_storage.apiUrl}/auth/refresh',
        data: {'refresh_token': session.refreshToken},
      );
      final next = AuthSession.fromJson(res.data as Map<String, dynamic>);
      await _storage.setSession(next);
      return true;
    } catch (_) {
      await _storage.setSession(null);
      return false;
    }
  }

  Future<AuthSession> driverLogin(String phone, String password) async {
    final res = await _dio.post(
      '${_storage.apiUrl}/driver/login',
      data: {'phone': phone, 'password': password},
    );
    final map = Map<String, dynamic>.from(res.data as Map);
    final session = AuthSession.fromJson(map);
    await _storage.setSession(session);

    final driverJson = map['driver'] as Map<String, dynamic>?;
    if (driverJson != null) {
      final driver = Driver.fromJson(driverJson);
      await _storage.setDriverId(driver.id);
      await _storage.setDriverType(driver.driverType);
    }

    final vehicleJson = map['vehicle'] as Map<String, dynamic>?;
    if (vehicleJson != null) {
      final vehicleId = vehicleJson['id'] as int?;
      if (vehicleId != null) {
        await _storage.setVehicleId(vehicleId);
      }
    }
    return session;
  }

  Future<List<Vehicle>> fetchVehicles() async {
    final res = await _request('GET', '/gps/vehicles');
    final list = (res.data as Map)['vehicles'] as List<dynamic>? ?? [];
    return list.map((e) => Vehicle.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  Future<List<Driver>> fetchDrivers() async {
    final res = await _request('GET', '/gps/drivers');
    final list = (res.data as Map)['drivers'] as List<dynamic>? ?? [];
    return list.map((e) => Driver.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  Future<List<TransportTask>> fetchDriverTasks({String status = ''}) async {
    final res = await _request(
      'GET',
      '/driver/tasks',
      query: status.isEmpty ? null : {'status': status},
    );
    final list = (res.data as Map)['tasks'] as List<dynamic>? ?? [];
    return list.map((e) => TransportTask.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  Future<void> postGpsUpdate(Map<String, dynamic> payload) async {
    await _request('POST', '/gps/update', data: payload);
  }

  Future<void> startTask(int taskId) async {
    await _request('POST', '/driver/tasks/$taskId/start');
  }

  Future<void> completeTask(int taskId) async {
    await _request('POST', '/driver/tasks/$taskId/complete');
  }

  Future<List<ChatMessage>> fetchMessages({int sinceId = 0}) async {
    final res = await _request(
      'GET',
      '/driver/messages',
      query: sinceId > 0 ? {'since_id': sinceId} : null,
    );
    final list = (res.data as Map)['messages'] as List<dynamic>? ?? [];
    return list.map((e) => ChatMessage.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  Future<ChatMessage> sendMessage(String content) async {
    final res = await _request('POST', '/driver/messages', data: {'content': content});
    final msg = (res.data as Map)['message'] as Map<String, dynamic>;
    return ChatMessage.fromJson(msg);
  }

  Future<ChatMessage> uploadPhoto(String filePath, {String caption = ''}) async {
    final session = _storage.session;
    if (session == null) throw ApiException('Not logged in');

    final form = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath, filename: filePath.split('/').last),
      'caption': caption,
    });

    try {
      final res = await _dio.post(
        '${_storage.apiUrl}/driver/photo',
        data: form,
        options: Options(
          headers: {'Authorization': 'Bearer ${session.accessToken}'},
          contentType: 'multipart/form-data',
        ),
      );
      final msg = (res.data as Map)['message'] as Map<String, dynamic>;
      return ChatMessage.fromJson(msg);
    } on DioException catch (e) {
      final detail = e.response?.data;
      var message = e.message ?? 'Upload failed';
      if (detail is Map && detail['detail'] != null) {
        message = detail['detail'].toString();
      }
      throw ApiException(message, statusCode: e.response?.statusCode);
    }
  }

  String resolveMediaUrl(String? path) {
    if (path == null || path.isEmpty) return '';
    if (path.startsWith('http')) return path;
    return '${_storage.apiUrl}$path';
  }
}

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}
