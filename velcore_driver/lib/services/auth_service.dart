import '../models/auth_session.dart';
import '../models/driver.dart';
import 'api_service.dart';
import 'storage_service.dart';

class AuthService {
  AuthService(this._storage, this._api);

  final StorageService _storage;
  final ApiService _api;

  AuthSession? get session => _storage.session;

  bool get isLoggedIn => session != null;

  String get driverType => _storage.driverType;

  Future<AuthSession> login(String phone, String password) async {
    final session = await _api.driverLogin(phone, password);
    await _storage.setDriverPhone(phone);
    return session;
  }

  Future<void> logout() async {
    await _storage.setSession(null);
    await _storage.setDriverId(null);
    await _storage.setDriverType('');
    await _storage.setVehicleId(null);
    await _storage.setTrackingActive(false);
  }

  Future<Driver?> resolveDriver(String phone) async {
    final drivers = await _api.fetchDrivers();
    for (final d in drivers) {
      if (d.matchesPhone(phone)) return d;
    }
    return null;
  }
}
