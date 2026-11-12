import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../util.dart';
import '../widgets/api_image.dart';
import '../payroll.dart';
import 'leave.dart';
import 'payroll.dart';

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
      Container(
        margin: const EdgeInsets.all(16),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(colors: [Color(0xFF2F54EB), Color(0xFF7B1FA2)], begin: Alignment.topLeft, end: Alignment.bottomRight),
          borderRadius: BorderRadius.circular(24),
        ),
        child: Row(children: [
          Avatar(person, radius: 32),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(displayName(person), style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w800)),
              const SizedBox(height: 2),
              Text('${me['role']?['name'] ?? (me['is_super_admin'] == true ? 'Super Admin' : '')}', style: const TextStyle(color: Colors.white70)),
              Text('${me['email'] ?? ''}', style: const TextStyle(color: Colors.white70, fontSize: 12)),
            ]),
          ),
        ]),
      ),
      if (state.inTeam) ListTile(leading: const CircleAvatar(backgroundColor: Color(0x1FF57C00), child: Icon(Icons.event_busy_outlined, color: Color(0xFFF57C00))), title: const Text('Leave'), trailing: const Icon(Icons.chevron_right), onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const LeaveScreen()))),
      if (canManagePayroll(me))
        ListTile(
          leading: const CircleAvatar(backgroundColor: Color(0x1F2F54EB), child: Icon(Icons.payments_outlined, color: Color(0xFF2F54EB))),
          title: const Text('Payroll'),
          subtitle: const Text('Salaries, word counts, hours and rates'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const PayrollScreen())),
        ),
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
