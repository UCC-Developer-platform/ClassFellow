import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../../models/user_session.dart';

/// Service providing persistent, encrypted storage for user auth tokens and profile.
class SecureStorageService {
  final FlutterSecureStorage _storage;
  final Map<String, String> _memoryFallback = {};
  final bool useMemoryFallback;

  static const String _keyToken = 'auth_token';
  static const String _keyUserId = 'user_id';
  static const String _keyUsername = 'username';
  static const String _keyRole = 'user_role';
  static const String _keyFullName = 'full_name';

  SecureStorageService({
    FlutterSecureStorage? storage,
    this.useMemoryFallback = false,
  }) : _storage = storage ?? const FlutterSecureStorage();

  Future<void> write(String key, String value) async {
    if (useMemoryFallback) {
      _memoryFallback[key] = value;
      return;
    }
    try {
      await _storage.write(key: key, value: value);
    } catch (_) {
      _memoryFallback[key] = value;
    }
  }

  Future<String?> read(String key) async {
    if (useMemoryFallback) {
      return _memoryFallback[key];
    }
    try {
      return await _storage.read(key: key);
    } catch (_) {
      return _memoryFallback[key];
    }
  }

  Future<void> delete(String key) async {
    if (useMemoryFallback) {
      _memoryFallback.remove(key);
      return;
    }
    try {
      await _storage.delete(key: key);
    } catch (_) {
      _memoryFallback.remove(key);
    }
  }

  Future<void> clearAll() async {
    if (useMemoryFallback) {
      _memoryFallback.clear();
      return;
    }
    try {
      await _storage.deleteAll();
    } catch (_) {
      _memoryFallback.clear();
    }
  }

  Future<void> saveSession(UserSession session) async {
    await write(_keyToken, session.token);
    await write(_keyUserId, session.userId.toString());
    await write(_keyUsername, session.username);
    await write(_keyRole, session.role);
    await write(_keyFullName, session.fullName);
  }

  Future<UserSession?> getSession() async {
    final token = await read(_keyToken);
    final userIdStr = await read(_keyUserId);
    final username = await read(_keyUsername);
    final role = await read(_keyRole);
    final fullName = await read(_keyFullName);

    if (token == null || role == null || username == null) {
      return null;
    }

    return UserSession(
      token: token,
      userId: int.tryParse(userIdStr ?? '0') ?? 0,
      username: username,
      role: role,
      fullName: fullName ?? username,
    );
  }

  Future<String?> getToken() => read(_keyToken);
  Future<String?> getRole() => read(_keyRole);
  Future<bool> hasSession() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }
}
