class AuthSession {
  const AuthSession({
    required this.accessToken,
    required this.refreshToken,
    required this.username,
    required this.role,
    this.department = '',
  });

  final String accessToken;
  final String refreshToken;
  final String username;
  final String role;
  final String department;

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    return AuthSession(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      username: json['username'] as String? ?? '',
      role: json['role'] as String? ?? '',
      department: json['department'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'access_token': accessToken,
        'refresh_token': refreshToken,
        'username': username,
        'role': role,
        'department': department,
      };
}
