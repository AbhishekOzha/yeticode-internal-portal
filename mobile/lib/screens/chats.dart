import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../util.dart';
import '../widgets/api_image.dart';
import 'chat_screen.dart';

String lastText(Json? m) {
  if (m == null) return 'No messages yet';
  if (m['audio'] != null) return '🎤 Voice message';
  if (m['file'] != null) return '📎 ${m['file']['name']}';
  return (m['body'] ?? '').toString();
}

class ChatsScreen extends StatefulWidget {
  const ChatsScreen({super.key});
  @override
  State<ChatsScreen> createState() => _ChatsScreenState();
}

class _ChatsScreenState extends State<ChatsScreen> {
  Json? _data;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 4), (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final d = await api.get('/chat/contacts/');
      if (mounted) setState(() {
        _data = d;
        _error = null;
      });
    } catch (e) {
      if (mounted && _data == null) setState(() => _error = e.toString());
    }
  }

  Future<void> _open(String key, String title, {Json? peer, Json? group}) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => ChatScreen(convKey: key, title: title, peer: peer, group: group)));
    _load();
    if (mounted) context.read<AppState>().refreshUnread();
  }

  Future<void> _newGroup() async {
    final contacts = (_data!['contacts'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
    final name = TextEditingController();
    final chosen = <String>{};
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, set) => AlertDialog(
          title: const Text('New group'),
          content: SizedBox(
            width: double.maxFinite,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextField(controller: name, decoration: const InputDecoration(labelText: 'Group name')),
              Flexible(
                child: ListView(shrinkWrap: true, children: [
                  for (final c in contacts)
                    CheckboxListTile(
                      value: chosen.contains(c['id'].toString()),
                      title: Text(displayName(c)),
                      onChanged: (v) => set(() => v == true ? chosen.add(c['id'].toString()) : chosen.remove(c['id'].toString())),
                    ),
                ]),
              ),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Create')),
          ],
        ),
      ),
    );
    if (ok != true) return;
    try {
      final g = await api.post('/chat/groups/', {'name': name.text, 'members': chosen.toList()});
      await _load();
      if (mounted) _open(g!['key'], g['name'], group: g);
    } catch (e) {
      if (mounted) toast(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    if (_data == null) return Center(child: _error != null ? Padding(padding: const EdgeInsets.all(24), child: Text(_error!)) : const CircularProgressIndicator());
    final team = Map<String, dynamic>.from(_data!['team']);
    final groups = (_data!['groups'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
    final contacts = (_data!['contacts'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
    Widget badge(int n) => n > 0 ? Badge(label: Text('$n')) : const SizedBox.shrink();
    return Scaffold(
      floatingActionButton: FloatingActionButton(onPressed: _newGroup, tooltip: 'New group', child: const Icon(Icons.group_add)),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(children: [
          ListTile(
            leading: const CircleAvatar(child: Icon(Icons.groups)),
            title: const Text('Team room', style: TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text(lastText(team['last_message']), maxLines: 1, overflow: TextOverflow.ellipsis),
            trailing: badge((state.unread['team'] ?? team['unread'] ?? 0) as int),
            onTap: () => _open('team', 'Team room'),
          ),
          for (final g in groups)
            ListTile(
              leading: const CircleAvatar(child: Icon(Icons.group)),
              title: Text(g['name'], style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text(lastText(g['last_message']), maxLines: 1, overflow: TextOverflow.ellipsis),
              trailing: badge((state.unread[g['key']] ?? g['unread'] ?? 0) as int),
              onTap: () => _open(g['key'], g['name'], group: g),
            ),
          const Divider(),
          for (final c in contacts)
            ListTile(
              leading: Avatar(c, online: state.isOnline(c['id'])),
              title: Text(displayName(c), style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text(lastText(c['last_message']), maxLines: 1, overflow: TextOverflow.ellipsis),
              trailing: badge((state.unread[c['id'].toString()] ?? c['unread'] ?? 0) as int),
              onTap: () => _open(c['id'].toString(), displayName(c), peer: c),
            ),
        ]),
      ),
    );
  }
}
