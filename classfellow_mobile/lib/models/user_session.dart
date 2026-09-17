/// Represents the authenticated user profile and security token.
class UserSession {
  final String token;
  final int userId;
  final String username;
  final String role;
  final String fullName;

  const UserSession({
    required this.token,
    required this.userId,
    required this.username,
    required this.role,
    required this.fullName,
  });

  bool get isTeacher => role.toLowerCase() == 'teacher';
  bool get isParent => role.toLowerCase() == 'parent';
  bool get isAdmin => role.toLowerCase() == 'admin' || role.toLowerCase() == 'principal';

  factory UserSession.fromJson(Map<String, dynamic> json) {
    return UserSession(
      token: json['token'] as String? ?? '',
      userId: json['user_id'] as int? ?? 0,
      username: json['username'] as String? ?? '',
      role: json['role'] as String? ?? '',
      fullName: json['full_name'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'token': token,
      'user_id': userId,
      'username': username,
      'role': role,
      'full_name': fullName,
    };
  }
}
