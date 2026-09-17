import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import '../lib/core/network/api_client.dart';

void main() {
  group('ApiClient Unit Tests', () {
    test('Token header is attached when setAuthToken is called', () async {
      String? capturedHeader;

      final mockClient = MockClient((request) async {
        capturedHeader = request.headers['Authorization'];
        return http.Response(jsonEncode({'status': 'ok'}), 200);
      });

      final apiClient = ApiClient(
        baseUrl: 'http://example.com',
        client: mockClient,
      );

      apiClient.setAuthToken('secret-test-token');
      final response = await apiClient.get('/api/v1/test/');

      expect(capturedHeader, equals('Token secret-test-token'));
      expect(response, equals({'status': 'ok'}));
    });

    test('Unauthorized exception is thrown on 401 response', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Invalid token credentials'}),
          401,
        );
      });

      final apiClient = ApiClient(
        baseUrl: 'http://example.com',
        client: mockClient,
      );

      expect(
        () async => await apiClient.get('/api/v1/protected/'),
        throwsA(isA<UnauthorizedException>()),
      );
    });

    test('ApiException is thrown with status code on 500 error', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({'error': 'Internal server fault'}),
          500,
        );
      });

      final apiClient = ApiClient(
        baseUrl: 'http://example.com',
        client: mockClient,
      );

      try {
        await apiClient.get('/api/v1/fail/');
        fail('Expected ApiException');
      } on ApiException catch (e) {
        expect(e.statusCode, equals(500));
        expect(e.message, contains('Internal server fault'));
      }
    });
  });
}
