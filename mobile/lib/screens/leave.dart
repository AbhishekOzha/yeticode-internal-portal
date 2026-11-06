import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api.dart';
import '../util.dart';

class LeaveScreen extends StatefulWidget {
  const LeaveScreen({super.key});
  @override
  State<LeaveScreen> createState() => _LeaveScreenState();
}

class _LeaveScreenState extends State<LeaveScreen> {
  Json? _data;
  List<Json> _team = [];
  bool _approver = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final d = await api.get('/team/leave/');
      List<Json> team = [];
      bool approver = false;
      try {
        final t = await api.get('/team/leave/requests/?status=pending');
        team = (t['requests'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
        approver = true;
      } on ApiError {
        approver = false;
      }
      if (mounted) setState(() {
        _data = d;
        _team = team;
        _approver = approver;
      });
    } catch (e) {
      if (mounted) toast(context, e);
    }
  }

  Future<void> _decide(Json l, String decision) async {
    try {
      await api.post('/team/leave/${l['id']}/decide/', {'decision': decision, 'note': ''});
      _load();
    } catch (e) {
      if (mounted) toast(context, e);
    }
  }

  Future<void> _cancel(Json l) async {
    try {
      await api.post('/team/leave/${l['id']}/cancel/');
      _load();
    } catch (e) {
      if (mounted) toast(context, e);
    }
  }

  Future<void> _apply() async {
    final kinds = (_data!['kinds'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
    final done = await showModalBottomSheet<bool>(context: context, isScrollControlled: true, builder: (_) => _ApplySheet(kinds: kinds, approvers: _data!['approvers']));
    if (done == true) _load();
  }

  Color _color(String s) => switch (s) { 'approved' => Colors.green, 'rejected' => Colors.red, 'cancelled' => Colors.grey, _ => Colors.orange };

  @override
  Widget build(BuildContext context) {
    final mine = (_data?['requests'] as List?)?.map((e) => Map<String, dynamic>.from(e)).toList() ?? [];
    return Scaffold(
      appBar: AppBar(title: const Text('Leave')),
      floatingActionButton: _data == null ? null : FloatingActionButton.extended(onPressed: _apply, icon: const Icon(Icons.add), label: const Text('Apply')),
      body: _data == null
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.only(bottom: 90), children: [
                if (_approver && _team.isNotEmpty) ...[
                  const Padding(padding: EdgeInsets.all(16), child: Text('Waiting for your decision', style: TextStyle(fontWeight: FontWeight.w700))),
                  for (final l in _team)
                    Card(
                      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${displayName(l['user'])} · ${l['kind_label']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                          Text('${l['start_date']} → ${l['end_date']} (${l['days']} day${l['days'] == 1 ? '' : 's'})'),
                          if ((l['reason'] as String).isNotEmpty) Text(l['reason']),
                          if (l['can_decide'] == true)
                            Row(children: [
                              TextButton(onPressed: () => _decide(l, 'reject'), child: const Text('Reject')),
                              FilledButton(onPressed: () => _decide(l, 'approve'), child: const Text('Approve')),
                            ]),
                        ]),
                      ),
                    ),
                ],
                const Padding(padding: EdgeInsets.all(16), child: Text('My requests', style: TextStyle(fontWeight: FontWeight.w700))),
                if (mine.isEmpty) const Padding(padding: EdgeInsets.all(24), child: Center(child: Text('No leave requests yet'))),
                for (final l in mine)
                  ListTile(
                    title: Text('${l['kind_label']} · ${l['days']} day${l['days'] == 1 ? '' : 's'}'),
                    subtitle: Text('${l['start_date']} → ${l['end_date']}${l['half_day'] == true ? ' (half day)' : ''}${(l['decision_note'] ?? '') != '' ? '\n${l['decision_note']}' : ''}'),
                    trailing: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Chip(label: Text(l['status'], style: const TextStyle(fontSize: 11, color: Colors.white)), backgroundColor: _color(l['status']), visualDensity: VisualDensity.compact),
                      if (l['status'] == 'pending') GestureDetector(onTap: () => _cancel(l), child: const Text('Cancel', style: TextStyle(fontSize: 12, color: Colors.red))),
                    ]),
                  ),
              ]),
            ),
    );
  }
}

class _ApplySheet extends StatefulWidget {
  const _ApplySheet({required this.kinds, required this.approvers});
  final List<Json> kinds;
  final dynamic approvers;
  @override
  State<_ApplySheet> createState() => _ApplySheetState();
}

class _ApplySheetState extends State<_ApplySheet> {
  late String _kind = widget.kinds.first['value'];
  DateTime _start = DateTime.now();
  DateTime _end = DateTime.now();
  bool _half = false, _busy = false;
  final _reason = TextEditingController();
  final _fmt = DateFormat('yyyy-MM-dd');

  Future<void> _pick(bool start) async {
    final d = await showDatePicker(context: context, initialDate: start ? _start : _end, firstDate: DateTime.now().subtract(const Duration(days: 30)), lastDate: DateTime.now().add(const Duration(days: 365)));
    if (d == null) return;
    setState(() {
      if (start) {
        _start = d;
        if (_end.isBefore(d)) _end = d;
      } else {
        _end = d;
      }
    });
  }

  Future<void> _submit() async {
    setState(() => _busy = true);
    try {
      await api.post('/team/leave/', {'kind': _kind, 'start_date': _fmt.format(_start), 'end_date': _fmt.format(_end), 'half_day': _half, 'reason': _reason.text});
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) {
        toast(context, e);
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final names = (widget.approvers as List).map((p) => displayName(p)).join(', ');
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Apply for leave', style: Theme.of(context).textTheme.titleLarge),
          if (names.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text('$names will be told.', style: Theme.of(context).textTheme.bodySmall)),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _kind,
            decoration: const InputDecoration(labelText: 'Type', border: OutlineInputBorder()),
            items: [for (final k in widget.kinds) DropdownMenuItem(value: k['value'] as String, child: Text(k['label']))],
            onChanged: (v) => setState(() => _kind = v!),
          ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: OutlinedButton(onPressed: () => _pick(true), child: Text('From ${_fmt.format(_start)}'))),
            const SizedBox(width: 8),
            Expanded(child: OutlinedButton(onPressed: () => _pick(false), child: Text('To ${_fmt.format(_end)}'))),
          ]),
          SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Half day'), value: _half, onChanged: (v) => setState(() => _half = v)),
          TextField(controller: _reason, maxLines: 3, decoration: const InputDecoration(labelText: 'Reason (optional)', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          FilledButton(onPressed: _busy ? null : _submit, child: Text(_busy ? 'Sending…' : 'Send request')),
        ]),
      ),
    );
  }
}
