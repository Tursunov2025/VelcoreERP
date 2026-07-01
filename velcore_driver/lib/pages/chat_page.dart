import 'dart:async';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../models/chat_message.dart';
import '../services/api_service.dart';

class ChatPage extends StatefulWidget {
  const ChatPage({super.key, required this.api});

  final ApiService api;

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _controller = TextEditingController();
  final _scroll = ScrollController();
  final _picker = ImagePicker();

  List<ChatMessage> _messages = [];
  bool _loading = true;
  String? _error;
  bool _sending = false;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _load(initial: true);
    _poll = Timer.periodic(const Duration(seconds: 5), (_) => _load());
  }

  @override
  void dispose() {
    _poll?.cancel();
    _controller.dispose();
    _scroll.dispose();
    super.dispose();
  }

  int get _lastId => _messages.isEmpty ? 0 : _messages.last.id;

  Future<void> _load({bool initial = false}) async {
    if (!initial && _sending) return;
    try {
      final since = initial ? 0 : _lastId;
      final batch = await widget.api.fetchMessages(sinceId: since);
      if (!mounted) return;
      setState(() {
        if (initial) {
          _messages = batch;
        } else if (batch.isNotEmpty) {
          final ids = _messages.map((m) => m.id).toSet();
          _messages = [..._messages, ...batch.where((m) => !ids.contains(m.id))];
        }
        _error = null;
        _loading = false;
      });
      if (batch.isNotEmpty) {
        await Future<void>.delayed(const Duration(milliseconds: 100));
        if (_scroll.hasClients) {
          _scroll.animateTo(
            _scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOut,
          );
        }
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _sendText() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      final msg = await widget.api.sendMessage(text);
      _controller.clear();
      setState(() {
        _messages = [..._messages, msg];
        _sending = false;
      });
    } catch (e) {
      setState(() => _sending = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _pickPhoto(ImageSource source) async {
    try {
      final file = await _picker.pickImage(source: source, maxWidth: 1920, imageQuality: 85);
      if (file == null) return;
      setState(() => _sending = true);
      final caption = _controller.text.trim();
      final msg = await widget.api.uploadPhoto(file.path, caption: caption);
      _controller.clear();
      if (!mounted) return;
      setState(() {
        _messages = [..._messages, msg];
        _sending = false;
      });
    } catch (e) {
      setState(() => _sending = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  void _showPhotoOptions() {
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera),
              title: const Text('Kamera'),
              onTap: () {
                Navigator.pop(ctx);
                _pickPhoto(ImageSource.camera);
              },
            ),
            ListTile(
              leading: const Icon(Icons.photo_library),
              title: const Text('Galereya'),
              onTap: () {
                Navigator.pop(ctx);
                _pickPhoto(ImageSource.gallery);
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Chat — Logistika'),
        actions: [
          IconButton(onPressed: () => _load(initial: true), icon: const Icon(Icons.refresh)),
        ],
      ),
      body: Column(
        children: [
          if (_error != null)
            MaterialBanner(
              content: Text(_error!),
              actions: [TextButton(onPressed: () => _load(initial: true), child: const Text('Qayta'))],
            ),
          Expanded(
            child: _loading && _messages.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.all(12),
                    itemCount: _messages.length,
                    itemBuilder: (context, i) {
                      final m = _messages[i];
                      return _MessageBubble(message: m, api: widget.api);
                    },
                  ),
          ),
          if (_sending) const LinearProgressIndicator(minHeight: 2),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
              child: Row(
                children: [
                  IconButton(
                    onPressed: _sending ? null : _showPhotoOptions,
                    icon: const Icon(Icons.add_a_photo_outlined),
                    tooltip: 'Foto yuborish',
                  ),
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      decoration: const InputDecoration(
                        hintText: 'Xabar yozing…',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _sendText(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    onPressed: _sending ? null : _sendText,
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message, required this.api});

  final ChatMessage message;
  final ApiService api;

  @override
  Widget build(BuildContext context) {
    final time = message.createdAt != null
        ? '${message.createdAt!.hour.toString().padLeft(2, '0')}:${message.createdAt!.minute.toString().padLeft(2, '0')}'
        : '';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            message.senderDepartment.isNotEmpty ? message.senderDepartment : message.senderUsername,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (message.isImage)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.network(
                      api.resolveMediaUrl(message.attachmentUrl),
                      loadingBuilder: (c, child, progress) {
                        if (progress == null) return child;
                        return const SizedBox(
                          height: 120,
                          child: Center(child: CircularProgressIndicator()),
                        );
                      },
                      errorBuilder: (_, __, ___) => const Text('Rasm yuklanmadi'),
                    ),
                  ),
                if (message.content.isNotEmpty) ...[
                  if (message.isImage) const SizedBox(height: 6),
                  Text(message.content),
                ],
                if (time.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(time, style: Theme.of(context).textTheme.labelSmall),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
