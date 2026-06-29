class TransportTask {
  const TransportTask({
    required this.id,
    required this.title,
    this.description = '',
    this.origin = '',
    this.destination = '',
    this.status = 'assigned',
    this.vehiclePlate,
    this.driverName,
  });

  final int id;
  final String title;
  final String description;
  final String origin;
  final String destination;
  final String status;
  final String? vehiclePlate;
  final String? driverName;

  factory TransportTask.fromJson(Map<String, dynamic> json) {
    final vehicle = json['vehicle'] as Map<String, dynamic>?;
    final driver = json['driver'] as Map<String, dynamic>?;
    return TransportTask(
      id: json['id'] as int,
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      origin: json['origin'] as String? ?? '',
      destination: json['destination'] as String? ?? '',
      status: json['status'] as String? ?? 'assigned',
      vehiclePlate: vehicle?['plate_number'] as String?,
      driverName: driver?['full_name'] as String?,
    );
  }
}
