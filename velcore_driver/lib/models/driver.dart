class Driver {
  const Driver({
    required this.id,
    required this.fullName,
    this.phone = '',
    this.status = 'active',
  });

  final int id;
  final String fullName;
  final String phone;
  final String status;

  factory Driver.fromJson(Map<String, dynamic> json) {
    return Driver(
      id: json['id'] as int,
      fullName: json['full_name'] as String? ?? '',
      phone: json['phone'] as String? ?? '',
      status: json['status'] as String? ?? 'active',
    );
  }

  static String normalizePhone(String phone) {
    return phone.replaceAll(RegExp(r'\D'), '');
  }

  bool matchesPhone(String phone) {
    final a = normalizePhone(this.phone);
    final b = normalizePhone(phone);
    if (a.isEmpty || b.isEmpty) return false;
    if (a == b) return true;
    if (a.endsWith(b) || b.endsWith(a)) return true;
    if (a.length >= 9 && b.length >= 9 && a.substring(a.length - 9) == b.substring(b.length - 9)) {
      return true;
    }
    return false;
  }
}
