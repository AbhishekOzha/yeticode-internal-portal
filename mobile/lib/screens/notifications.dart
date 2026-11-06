import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../util.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});
  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<Json> _items = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await api.get('/notifications/');
      if (mounted) setState(() {
        _items = (res['notifications'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
        _loading = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _readAll() async {
    await api.post('/notifications/read/', {});
    if (mounted) context.read<AppState>().refreshNotes();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications'), actions: [TextButton(onPressed: _readAll, child: const Text('Mark all read'))]),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? const Center(child: Text('Nothing new'))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(children: [
                    for (final n in _items)
                      ListTile(
                        leading: Icon(n['read'] == true ? Icons.notifications_none : Icons.notifications_active, color: n['read'] == true ? null : Theme.of(context).colorScheme.primary),
                        title: Text(n['title'], style: TextStyle(fontWeight: n['read'] == true ? FontWeight.normal : FontWeight.w600)),
                        subtitle: Text(n['body'] ?? ''),
                        trailing: Text(timeAgo(n['created_at']), style: const TextStyle(fontSize: 11)),
                      ),
                  ]),
                ),
    );
  }
}
