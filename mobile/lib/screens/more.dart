import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../util.dart';
import '../widgets/api_image.dart';
import 'leave.dart';

class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final me = state.me!;
    final person = {
      'full_name': me['full_name'] ?? '${me['first_name'] ?? ''} ${me['last_name'] ?? ''}'.trim(),
      'username': me['username'],
      'avatar': me['avatar'],
    };
    return ListView(children: [
      ListTile(
        contentPadding: const EdgeInsets.all(16),
        leading: Avatar(person, radius: 28),
        title: Text(displayName(person), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        subtitle: Text('${me['role']?['name'] ?? (me['is_super_admin'] == true ? 'Super Admin' : '')}\n${me['email'] ?? ''}'),
        isThreeLine: true,
      ),
      const Divider(),
      if (state.inTeam) ListTile(leading: const Icon(Icons.event_busy_outlined), title: const Text('Leave'), trailing: const Icon(Icons.chevron_right), onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const LeaveScreen()))),
      ListTile(leading: const Icon(Icons.dns_outlined), title: const Text('Server'), subtitle: Text(api.baseUrl)),
      ListTile(
        leading: const Icon(Icons.logout),
        title: const Text('Sign out'),
        onTap: () async {
          await state.signOut();
          if (context.mounted) toast(context, 'Signed out');
        },
      ),
    ]);
  }
}
