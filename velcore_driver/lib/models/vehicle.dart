class Vehicle {
  const Vehicle({
    required this.id,
    required this.plateNumber,
    this.model = '',
    this.status = 'active',
  });

  final int id;
  final String plateNumber;
  final String model;
  final String status;

  factory Vehicle.fromJson(Map<String, dynamic> json) {
    return Vehicle(
      id: json['id'] as int,
      plateNumber: json['plate_number'] as String? ?? '',
      model: json['model'] as String? ?? '',
      status: json['status'] as String? ?? 'active',
    );
  }

  String get label {
    if (model.isEmpty) return plateNumber;
    return '$plateNumber · $model';
  }
}
