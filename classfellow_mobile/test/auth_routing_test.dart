import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import '../lib/core/network/api_client.dart';
import '../lib/core/storage/secure_storage_service.dart';
import '../lib/features/auth/auth_controller.dart';
import '../lib/models/user_session.dart';

void main() {
  group('AuthController & Session Routing Tests', () {
    test('Successful teacher login persists session and sets api client token', () async {
      final mockClient = MockClient((request) async {
        if (request.url.path.contains('/api/v1/auth/login/')) {
          return http.Response(
            jsonEncode({
              'token': 'auth-token-teacher-99',
              'user_id': 42,
              'username': 'teacher.ahmed',
              'role': 'TEACHER',
              'full_name': 'Ahmed Raza',
            }),
            200,
          );
        }
        return http.Response('Not Found', 404);
      });

      final storage = SecureStorageService(inMemoryForTesting: true);
      final apiClient = ApiClient(baseUrl: 'http://testserver', client: mockClient);
      final controller = AuthController(apiClient: apiClient, storageService: storage);

      final success = await controller.login('teacher.ahmed', 'Secret123!');
      expect(success, isTrue);
      expect(controller.isAuthenticated, isTrue);
      expect(controller.session?.isTeacher, isTrue);
      expect(controller.session?.isParent, isFalse);
      expect(apiClient.authToken, equals('auth-token-teacher-99'));

      // Verify secure storage has it
      final storedSession = await storage.getSession();
      expect(storedSession?.token, equals('auth-token-teacher-99'));
    });

    test('Successful parent login sets role to PARENT', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'token': 'auth-token-parent-88',
            'user_id': 50,
            'username': 'parent.aslam',
            'role': 'PARENT',
            'full_name': 'Mohammad Aslam',
          }),
          200,
        );
      });

      final storage = SecureStorageService(inMemoryForTesting: true);
      final apiClient = ApiClient(baseUrl: 'http://testserver', client: mockClient);
      final controller = AuthController(apiClient: apiClient, storageService: storage);

      final success = await controller.login('parent.aslam', 'Secret123!');
      expect(success, isTrue);
      expect(controller.session?.isParent, isTrue);
      expect(controller.session?.isTeacher, isFalse);
    });

    test('Empty credentials reject without network call', () async {
      final storage = SecureStorageService(inMemoryForTesting: true);
      final apiClient = ApiClient(baseUrl: 'http://testserver');
      final controller = AuthController(apiClient: apiClient, storageService: storage);

      final success = await controller.login('', '');
      expect(success, isFalse);
      expect(controller.errorMessage, contains('cannot be empty'));
      expect(controller.isAuthenticated, isFalse);
    });

    test('Logout clears session, token, and storage', () async {
      final storage = SecureStorageService(inMemoryForTesting: true);
      await storage.saveSession(
        const UserSession(
          token: 'active-token',
          userId: 1,
          username: 'user1',
          role: 'TEACHER',
          fullName: 'User One',
        ),
      );

      final apiClient = ApiClient(baseUrl: 'http://testserver');
      final controller = AuthController(apiClient: apiClient, storageService: storage);

      await controller.tryAutoLogin();
      expect(controller.isAuthenticated, isTrue);

      await controller.logout();
      expect(controller.isAuthenticated, isFalse);
      expect(controller.session, isNull);
      expect(apiClient.authToken, isNull);

      final storedAfterLogout = await storage.getSession();
      expect(storedAfterLogout, isNull);
    });
  });
}
