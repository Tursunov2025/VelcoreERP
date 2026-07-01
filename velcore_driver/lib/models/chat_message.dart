class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.senderUsername,
    this.senderDepartment = '',
    this.content = '',
    this.messageType = 'text',
    this.attachmentUrl,
    this.createdAt,
  });

  final int id;
  final String senderUsername;
  final String senderDepartment;
  final String content;
  final String messageType;
  final String? attachmentUrl;
  final DateTime? createdAt;

  bool get isImage => messageType == 'image' && (attachmentUrl?.isNotEmpty ?? false);

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    DateTime? created;
    final raw = json['created_at'];
    if (raw is String) created = DateTime.tryParse(raw);
    return ChatMessage(
      id: json['id'] as int,
      senderUsername: json['sender_username'] as String? ?? '',
      senderDepartment: json['sender_department'] as String? ?? '',
      content: json['content'] as String? ?? '',
      messageType: json['message_type'] as String? ?? 'text',
      attachmentUrl: json['attachment_url'] as String?,
      createdAt: created,
    );
  }
}
