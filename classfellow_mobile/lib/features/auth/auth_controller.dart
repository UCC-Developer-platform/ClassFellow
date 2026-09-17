import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../core/storage/secure_storage_service.dart';
import '../../models/user_session.dart';

class AuthController extends ChangeNotifier {
  final ApiClient apiClient;
  final SecureStorageService storageService;

  UserSession? _session;
  bool _isLoading = false;
  String? _errorMessage;

  AuthController({
    required this.apiClient,
    required this.storageService,
  });

  UserSession? get session => _session;
  bool get isAuthenticated => _session != null && _session!.token.isNotEmpty;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<bool> tryAutoLogin() async {
    _isLoading = true;
    notifyListeners();

    try {
      final savedSession = await storageService.getSession();
      if (savedSession != null && savedSession.token.isNotEmpty) {
        _session = savedSession;
        apiClient.setAuthToken(savedSession.token);
        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (_) {
      // Ignored - fallback to unauthenticated state
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }

  Future<bool> login(String username, String password) async {
    if (username.trim().isEmpty || password.trim().isEmpty) {
      _errorMessage = 'Username and password cannot be empty.';
      notifyListeners();
      return false;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await apiClient.post(
        ApiEndpoints.login,
        body: {
          'username': username.trim(),
          'password': password,
        },
      );

      if (response is Map<String, dynamic>) {
        final newSession = UserSession.fromJson(response);
        _session = newSession;
        apiClient.setAuthToken(newSession.token);
        await storageService.saveSession(newSession);
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        throw const ApiException(
          statusCode: 500,
          message: 'Invalid response format received from login endpoint.',
        );
      }
    } on ApiException catch (e) {
      _errorMessage = e.message;
    } on UnauthorizedException catch (e) {
      _errorMessage = e.message;
    } on NetworkTimeoutException catch (e) {
      _errorMessage = e.message;
    } catch (e) {
      _errorMessage = 'Login failed: ${e.toString()}';
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }

  Future<void> logout() async {
    _session = null;
    _errorMessage = null;
    apiClient.clearAuthToken();
    await storageService.clearSession();
    notifyListeners();
  }
}
