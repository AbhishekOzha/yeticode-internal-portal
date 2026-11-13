import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'api.dart';

String displayName(Json? p) {
  if (p == null) return '';
  final name = (p['full_name'] ?? '').toString().trim();
  return name.isEmpty ? (p['username'] ?? '').toString() : name;
}

String initials(Json? p) {
  final parts = displayName(p).split(RegExp(r'\s+')).where((s) => s.isNotEmpty).toList();
  if (parts.isEmpty) return '?';
  return (parts.first[0] + (parts.length > 1 ? parts.last[0] : '')).toUpperCase();
}

String timeAgo(String iso) {
  final t = DateTime.tryParse(iso)?.toLocal();
  if (t == null) return '';
  final d = DateTime.now().difference(t);
  if (d.inMinutes < 1) return 'now';
  if (d.inMinutes < 60) return '${d.inMinutes}m';
  if (d.inHours < 24) return '${d.inHours}h';
  if (d.inDays < 7) return '${d.inDays}d';
  return DateFormat('d MMM').format(t);
}

String clock(String iso) {
  final t = DateTime.tryParse(iso)?.toLocal();
  return t == null ? '' : DateFormat('HH:mm').format(t);
}

String mmss(int seconds) => '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';

void toast(BuildContext context, Object message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message.toString())));
}

/// "Tell them about this change?" true = notify, false = save quietly.
Future<bool> askNotify(BuildContext context, String who, String what) async {
  final answer = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text('Notify $who?'),
      content: Text('Send $who a notification about $what.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('No, just save')),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Yes, notify')),
      ],
    ),
  );
  return answer ?? false;
}
