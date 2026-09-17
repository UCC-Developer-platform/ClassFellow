import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'api_endpoints.dart';

class ApiException implements Exception {
  final int statusCode;
  final String message;
  final dynamic data;

  const ApiException({
    required this.statusCode,
    required this.message,
    this.data,
  });

  @override
  String toString() => 'ApiException [$statusCode]: $message';
}

class NetworkTimeoutException implements Exception {
  final String message;
  const NetworkTimeoutException([this.message = 'Network request timed out after 10 seconds.']);

  @override
  String toString() => message;
}

class UnauthorizedException implements Exception {
  final String message;
  const UnauthorizedException([this.message = 'Session expired or invalid authentication token.']);

  @override
  String toString() => message;
}

class ApiClient {
  final String baseUrl;
  final http.Client _client;
  String? _authToken;

  ApiClient({
    String? baseUrl,
    http.Client? client,
  })  : baseUrl = baseUrl ?? ApiEndpoints.baseUrl,
        _client = client ?? http.Client();

  String? get authToken => _authToken;

  void setAuthToken(String? token) {
    _authToken = token;
  }

  void clearAuthToken() {
    _authToken = null;
  }

  Map<String, String> _buildHeaders() {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (_authToken != null && _authToken!.isNotEmpty) {
      headers['Authorization'] = 'Token $_authToken';
    }
    return headers;
  }

  Uri _buildUri(String path, [Map<String, String>? queryParams]) {
    final cleanPath = path.startsWith('/') ? path : '/$path';
    final uri = Uri.parse('$baseUrl$cleanPath');
    if (queryParams != null && queryParams.isNotEmpty) {
      return uri.replace(queryParameters: queryParams);
    }
    return uri;
  }

  Future<dynamic> get(
    String endpoint, {
    Map<String, String>? queryParams,
    Duration timeout = const Duration(seconds: 10),
  }) async {
    final uri = _buildUri(endpoint, queryParams);
    try {
      final response = await _client
          .get(uri, headers: _buildHeaders())
          .timeout(timeout);
      return _processResponse(response);
    } on TimeoutException {
      throw const NetworkTimeoutException();
    } on SocketException catch (e) {
      throw ApiException(statusCode: 0, message: 'Network connection error: ${e.message}');
    }
  }

  Future<dynamic> post(
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, String>? queryParams,
    Duration timeout = const Duration(seconds: 10),
  }) async {
    final uri = _buildUri(endpoint, queryParams);
    try {
      final response = await _client
          .post(
            uri,
            headers: _buildHeaders(),
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(timeout);
      return _processResponse(response);
    } on TimeoutException {
      throw const NetworkTimeoutException();
    } on SocketException catch (e) {
      throw ApiException(statusCode: 0, message: 'Network connection error: ${e.message}');
    }
  }

  dynamic _processResponse(http.Response response) {
    final statusCode = response.statusCode;
    dynamic decodedBody;

    if (response.body.isNotEmpty) {
      try {
        decodedBody = jsonDecode(response.body);
      } catch (_) {
        decodedBody = response.body;
      }
    }

    if (statusCode >= 200 && statusCode < 300) {
      return decodedBody;
    }

    if (statusCode == 401 || statusCode == 403) {
      String msg = 'Unauthorized access.';
      if (decodedBody is Map && decodedBody.containsKey('detail')) {
        msg = decodedBody['detail'].toString();
      } else if (decodedBody is Map && decodedBody.containsKey('error')) {
        msg = decodedBody['error'].toString();
      }
      throw UnauthorizedException(msg);
    }

    String message = 'API error occurred.';
    if (decodedBody is Map) {
      if (decodedBody.containsKey('detail')) {
        message = decodedBody['detail'].toString();
      } else if (decodedBody.containsKey('error')) {
        message = decodedBody['error'].toString();
      } else if (decodedBody.containsKey('message')) {
        message = decodedBody['message'].toString();
      } else {
        message = decodedBody.toString();
      }
    } else if (decodedBody is String && decodedBody.isNotEmpty) {
      message = decodedBody;
    }

    throw ApiException(
      statusCode: statusCode,
      message: message,
      data: decodedBody,
    );
  }

  void dispose() {
    _client.close();
  }
}
