import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api.dart';
import '../payroll.dart';
import '../util.dart';
import '../widgets/api_image.dart';

const _gradient = LinearGradient(colors: [Color(0xFF2F54EB), Color(0xFF7B1FA2)], begin: Alignment.topLeft, end: Alignment.bottomRight);

/// Payroll for the Academic Content Writing team: everyone's salary, extras (words and hours) and total for a month.
class PayrollScreen extends StatefulWidget {
  const PayrollScreen({super.key});
  @override
  State<PayrollScreen> createState() => _PayrollScreenState();
}

class _PayrollScreenState extends State<PayrollScreen> {
  String _month = currentMonth();
  List<Json> _staff = [];
  final Map<String, num> _words = {}, _hours = {};
  bool _loading = true;
  String? _error;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = _staff.isEmpty;
    });
    try {
      final staff = await api.get('/payroll/staff/?month=$_month');
      final extras = await api.getList('/payroll/extras/?month=$_month');
      _words.clear();
      _hours.clear();
      for (final e in extras) {
        final id = e['staff'].toString();
        final q = num.tryParse('${e['quantity'] ?? 0}') ?? 0;
        if (e['kind'] == 'words') _words[id] = (_words[id] ?? 0) + q;
        if (e['kind'] == 'hours') _hours[id] = (_hours[id] ?? 0) + q;
      }
      if (mounted) setState(() {
        _staff = (staff['staff'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
        _loading = false;
        _error = null;
      });
    } catch (e) {
      if (mounted) setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  void _go(int delta) {
    setState(() {
      _month = shiftMonth(_month, delta);
      _staff = [];
    });
    _load();
  }

  num _sum(Iterable<num> values) => values.fold<num>(0, (a, b) => a + b);

  @override
  Widget build(BuildContext context) {
    final total = _sum(_staff.map((s) => num.tryParse('${s['total']}') ?? 0));
    final salaries = _sum(_staff.map((s) => num.tryParse('${s['pay']['monthly_salary'] ?? 0}') ?? 0));
    final words = _sum(_words.values);
    final hours = _sum(_hours.values);
    final shown = _staff.where((s) => '${displayName(s)} ${s['role']}'.toLowerCase().contains(_query.toLowerCase())).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Payroll')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
          Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: Theme.of(context).colorScheme.secondaryContainer, borderRadius: BorderRadius.circular(14)),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(Icons.info_outline, color: Theme.of(context).colorScheme.onSecondaryContainer),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Payroll is only for the Academic Content Writing team at the moment. Other teams will be added in a later update.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSecondaryContainer),
                ),
              ),
            ]),
          ),
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            IconButton.filledTonal(onPressed: () => _go(-1), icon: const Icon(Icons.chevron_left)),
            Text(monthLabel(_month), style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            IconButton.filledTonal(onPressed: _month == currentMonth() ? null : () => _go(1), icon: const Icon(Icons.chevron_right)),
          ]),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(gradient: _gradient, borderRadius: BorderRadius.circular(24), boxShadow: [BoxShadow(color: const Color(0xFF2F54EB).withValues(alpha: 0.35), blurRadius: 20, offset: const Offset(0, 8))]),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Total payout this month', style: TextStyle(color: Colors.white70)),
              const SizedBox(height: 4),
              Text(npr(total), style: const TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.w800)),
              const SizedBox(height: 16),
              Row(children: [
                _Stat(Icons.people_alt_outlined, '${_staff.length}', 'Staff'),
                _Stat(Icons.edit_note, count(words), 'Words'),
                _Stat(Icons.schedule, count(hours), 'Hours'),
                _Stat(Icons.account_balance_wallet_outlined, npr(salaries).replaceFirst('NPR ', ''), 'Salaries'),
              ]),
            ]),
          ),
          const SizedBox(height: 16),
          TextField(
            onChanged: (v) => setState(() => _query = v),
            decoration: InputDecoration(prefixIcon: const Icon(Icons.search), hintText: 'Search staff', filled: true, border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none), isDense: true),
          ),
          const SizedBox(height: 8),
          if (_loading) const Padding(padding: EdgeInsets.all(48), child: Center(child: CircularProgressIndicator())),
          if (_error != null) Padding(padding: const EdgeInsets.all(24), child: Text(_error!)),
          for (final s in shown) _StaffCard(staff: s, words: _words[s['id'].toString()] ?? 0, hours: _hours[s['id'].toString()] ?? 0, month: _month, onChanged: _load),
        ]),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat(this.icon, this.value, this.label);
  final IconData icon;
  final String value, label;
  @override
  Widget build(BuildContext context) => Expanded(
        child: Column(children: [
          Icon(icon, color: Colors.white70, size: 20),
          const SizedBox(height: 4),
          FittedBox(child: Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15))),
          Text(label, style: const TextStyle(color: Colors.white70, fontSize: 11)),
        ]),
      );
}

class _StaffCard extends StatelessWidget {
  const _StaffCard({required this.staff, required this.words, required this.hours, required this.month, required this.onChanged});
  final Json staff;
  final num words, hours;
  final String month;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    final pay = Map<String, dynamic>.from(staff['pay']);
    final scheme = Theme.of(context).colorScheme;
    Widget chip(IconData icon, String text, Color color) => Container(
          margin: const EdgeInsets.only(right: 6, top: 8),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [Icon(icon, size: 13, color: color), const SizedBox(width: 4), Text(text, style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600))]),
        );
    return Card(
      elevation: 0,
      color: scheme.surfaceContainerLow,
      margin: const EdgeInsets.only(top: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () async {
          await Navigator.push(context, MaterialPageRoute(builder: (_) => StaffPayScreen(staff: staff, month: month)));
          onChanged();
        },
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Avatar(staff, radius: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(displayName(staff), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                Text('${staff['role']}', style: Theme.of(context).textTheme.bodySmall),
                Wrap(children: [
                  chip(Icons.payments_outlined, 'Salary ${npr(pay['monthly_salary'])}', Colors.indigo),
                  if (words > 0) chip(Icons.edit_note, '${count(words)} words', Colors.purple),
                  if (hours > 0) chip(Icons.schedule, '${count(hours)} h', Colors.teal),
                  if ((num.tryParse('${staff['leave_days']}') ?? 0) > 0) chip(Icons.event_busy, '${staff['leave_days']} leave', Colors.orange),
                ]),
              ]),
            ),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(npr(staff['total']), style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: scheme.primary)),
              const Text('total', style: TextStyle(fontSize: 11)),
            ]),
          ]),
        ),
      ),
    );
  }
}

/// One person's pay for the month: payslip, salary and hour/word rates, and their extras.
class StaffPayScreen extends StatefulWidget {
  const StaffPayScreen({super.key, required this.staff, required this.month});
  final Json staff;
  final String month;
  @override
  State<StaffPayScreen> createState() => _StaffPayScreenState();
}

class _StaffPayScreenState extends State<StaffPayScreen> {
  late Json _staff = widget.staff;
  Json? _slip;
  List<Json> _extras = [];
  bool _loading = true;

  String get _id => _staff['id'].toString();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final slip = await api.get('/payroll/staff/$_id/payslip/?month=${widget.month}');
      final extras = await api.getList('/payroll/extras/?month=${widget.month}&staff=$_id');
      if (mounted) setState(() {
        _slip = slip;
        _extras = extras;
        _loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() => _loading = false);
        toast(context, e);
      }
    }
  }

  Future<void> _editPay() async {
    final saved = await showModalBottomSheet<Json>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _PaySetupSheet(pay: Map<String, dynamic>.from(_staff['pay']), staffId: _id, month: widget.month),
    );
    if (saved != null) {
      setState(() => _staff = saved);
      _load();
    }
  }

  Future<void> _addExtra() async {
    final added = await showModalBottomSheet<bool>(context: context, isScrollControlled: true, builder: (_) => _ExtraSheet(staffId: _id, month: widget.month, pay: Map<String, dynamic>.from(_staff['pay'])));
    if (added == true) _load();
  }

  Future<void> _deleteExtra(Json e) async {
    try {
      await api.delete('/payroll/extras/${e['id']}/');
      _load();
    } catch (err) {
      if (mounted) toast(context, err);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pay = Map<String, dynamic>.from(_staff['pay']);
    final slip = _slip;
    final scheme = Theme.of(context).colorScheme;
    Widget row(String label, String value, {bool bold = false}) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 5),
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Text(label),
            Text(value, style: TextStyle(fontWeight: bold ? FontWeight.w800 : FontWeight.w500, fontSize: bold ? 17 : 14)),
          ]),
        );
    return Scaffold(
      appBar: AppBar(title: Text(displayName(_staff))),
      floatingActionButton: FloatingActionButton.extended(onPressed: _addExtra, icon: const Icon(Icons.add), label: const Text('Add extra')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 100), children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(gradient: _gradient, borderRadius: BorderRadius.circular(24)),
                child: Row(children: [
                  Avatar(_staff, radius: 30),
                  const SizedBox(width: 14),
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(displayName(_staff), style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)),
                    Text('${_staff['role']} · ${monthLabel(widget.month)}', style: const TextStyle(color: Colors.white70)),
                    const SizedBox(height: 8),
                    Text(npr(slip?['gross']), style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.w800)),
                    const Text('Gross for the month', style: TextStyle(color: Colors.white70, fontSize: 12)),
                  ])),
                ]),
              ),
              const SizedBox(height: 16),
              Card(
                elevation: 0,
                color: scheme.surfaceContainerLow,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(children: [
                    Row(children: [
                      const Expanded(child: Text('Salary & rates', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
                      TextButton.icon(onPressed: _editPay, icon: const Icon(Icons.edit, size: 16), label: const Text('Edit')),
                    ]),
                    row('Monthly salary', npr(pay['monthly_salary'])),
                    row('Word rate', '${count(pay['words_per_rate'])} words = ${npr(pay['words_rate_amount'])}'),
                    row('Hour rate', '${count(pay['hours_per_rate'])} hours = ${npr(pay['hours_rate_amount'])}'),
                  ]),
                ),
              ),
              if (slip != null)
                Card(
                  elevation: 0,
                  color: scheme.surfaceContainerLow,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(children: [
                      const Align(alignment: Alignment.centerLeft, child: Text('Payslip', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
                      row('Per day income', npr(slip['per_day'])),
                      row('Working days', '${slip['working_days']} of ${slip['total_days']}'),
                      row('Leave (unpaid)', '${slip['leave_days']} days'),
                      row('Salary amount', npr(slip['salary_amount'])),
                      row('Deducted for leave', npr(slip['leave_deduction'])),
                      row('Credits', '${slip['credits']} cr'),
                      row('Credit amount', npr(slip['credit_amount'])),
                      if ((num.tryParse('${slip['performance']}') ?? 0) > 0) row('Performance bonus', npr(slip['performance'])),
                      if ((num.tryParse('${slip['effort']}') ?? 0) > 0) row('Effort bonus', npr(slip['effort'])),
                      const Divider(),
                      row('Gross amount', npr(slip['gross']), bold: true),
                    ]),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: FilledButton.tonalIcon(
                  onPressed: () async {
                    await Navigator.push(context, MaterialPageRoute(builder: (_) => DailyLogScreen(staff: _staff, month: widget.month)));
                    _load();
                  },
                  icon: const Icon(Icons.calendar_month),
                  label: const Text('Daily log (hours & words by day)'),
                ),
              ),
              const Padding(padding: EdgeInsets.fromLTRB(4, 12, 4, 4), child: Text('Extras this month', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
              if (_extras.isEmpty) const Padding(padding: EdgeInsets.all(16), child: Text('No extras yet.')),
              for (final e in _extras)
                Dismissible(
                  key: ValueKey(e['id']),
                  direction: DismissDirection.endToStart,
                  confirmDismiss: (_) async => await showDialog<bool>(
                        context: context,
                        builder: (context) => AlertDialog(
                          title: const Text('Delete this extra?'),
                          actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete'))],
                        ),
                      ),
                  onDismissed: (_) => _deleteExtra(e),
                  background: Container(color: Colors.red, alignment: Alignment.centerRight, padding: const EdgeInsets.only(right: 20), child: const Icon(Icons.delete, color: Colors.white)),
                  child: ListTile(
                    leading: CircleAvatar(backgroundColor: _kindColor(e['kind']).withValues(alpha: 0.15), child: Icon(_kindIcon(e['kind']), color: _kindColor(e['kind']))),
                    title: Text(_kindLabel(e)),
                    subtitle: Text([if (e['date'] != null) DateFormat('d MMM').format(DateTime.parse(e['date'])), if ((e['note'] ?? '') != '') e['note']].join(' · ')),
                    trailing: Text(npr(e['amount']), style: const TextStyle(fontWeight: FontWeight.w700)),
                  ),
                ),
            ]),
    );
  }
}

Color _kindColor(String k) => switch (k) { 'words' => Colors.purple, 'hours' => Colors.teal, 'performance' => Colors.green, _ => Colors.orange };
IconData _kindIcon(String k) => switch (k) { 'words' => Icons.edit_note, 'hours' => Icons.schedule, 'performance' => Icons.trending_up, _ => Icons.local_fire_department };
String _kindLabel(Json e) => switch (e['kind']) {
      'words' => '${count(e['quantity'])} words',
      'hours' => '${count(e['quantity'])} hours',
      'performance' => 'Performance bonus',
      _ => 'Effort bonus',
    };

class _PaySetupSheet extends StatefulWidget {
  const _PaySetupSheet({required this.pay, required this.staffId, required this.month});
  final Json pay;
  final String staffId, month;
  @override
  State<_PaySetupSheet> createState() => _PaySetupSheetState();
}

class _PaySetupSheetState extends State<_PaySetupSheet> {
  late final _salary = TextEditingController(text: widget.pay['monthly_salary']?.toString().replaceAll(RegExp(r'\.00$'), '') ?? '');
  late final _wordsPer = TextEditingController(text: '${widget.pay['words_per_rate']}');
  late final _wordsAmt = TextEditingController(text: '${widget.pay['words_rate_amount']}'.replaceAll(RegExp(r'\.00$'), ''));
  late final _hoursPer = TextEditingController(text: '${widget.pay['hours_per_rate']}'.replaceAll(RegExp(r'\.00$'), ''));
  late final _hoursAmt = TextEditingController(text: '${widget.pay['hours_rate_amount']}'.replaceAll(RegExp(r'\.00$'), ''));
  bool _busy = false;

  Widget _field(String label, TextEditingController c, {String? prefix}) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: TextField(controller: c, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: label, prefixText: prefix, border: const OutlineInputBorder())),
      );

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      final saved = await api.patch('/payroll/staff/${widget.staffId}/?month=${widget.month}', {
        'monthly_salary': _salary.text.trim().isEmpty ? null : _salary.text.trim(),
        'words_per_rate': int.tryParse(_wordsPer.text.trim()) ?? 6000,
        'words_rate_amount': _wordsAmt.text.trim(),
        'hours_per_rate': _hoursPer.text.trim(),
        'hours_rate_amount': _hoursAmt.text.trim(),
      });
      if (mounted) Navigator.pop(context, saved);
    } catch (e) {
      if (mounted) {
        toast(context, e);
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Salary & rates', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          _field('Monthly salary (NPR)', _salary, prefix: 'NPR '),
          Row(children: [Expanded(child: _field('Words', _wordsPer)), const SizedBox(width: 8), Expanded(child: _field('Pays (NPR)', _wordsAmt))]),
          Row(children: [Expanded(child: _field('Hours', _hoursPer)), const SizedBox(width: 8), Expanded(child: _field('Pays (NPR)', _hoursAmt))]),
          FilledButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Save')),
        ]),
      ),
    );
  }
}

class _ExtraSheet extends StatefulWidget {
  const _ExtraSheet({required this.staffId, required this.month, required this.pay});
  final String staffId, month;
  final Json pay;
  @override
  State<_ExtraSheet> createState() => _ExtraSheetState();
}

class _ExtraSheetState extends State<_ExtraSheet> {
  String _kind = 'words';
  final _value = TextEditingController();
  final _note = TextEditingController();
  bool _busy = false;

  bool get _measured => _kind == 'words' || _kind == 'hours';

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      await api.post('/payroll/extras/', {
        'staff': widget.staffId,
        'month': widget.month,
        'kind': _kind,
        if (_measured) 'quantity': _value.text.trim() else 'amount': _value.text.trim(),
        'note': _note.text.trim(),
      });
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
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Add extra · ${monthLabel(widget.month)}', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'words', label: Text('Words')),
              ButtonSegment(value: 'hours', label: Text('Hours')),
              ButtonSegment(value: 'performance', label: Text('Perf.')),
              ButtonSegment(value: 'effort', label: Text('Effort')),
            ],
            selected: {_kind},
            onSelectionChanged: (v) => setState(() => _kind = v.first),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _value,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(labelText: switch (_kind) { 'words' => 'Words written', 'hours' => 'Hours worked', _ => 'Amount (NPR)' }, border: const OutlineInputBorder()),
          ),
          if (_measured)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(_kind == 'words' ? 'Paid at ${count(widget.pay['words_per_rate'])} words = ${npr(widget.pay['words_rate_amount'])}' : 'Paid at ${count(widget.pay['hours_per_rate'])} hours = ${npr(widget.pay['hours_rate_amount'])}', style: Theme.of(context).textTheme.bodySmall),
            ),
          const SizedBox(height: 12),
          TextField(controller: _note, decoration: const InputDecoration(labelText: 'Note (optional)', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          FilledButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Add')),
        ]),
      ),
    );
  }
}

/// Day-by-day extra hours and words for one person and month, like the website's daily log.
class DailyLogScreen extends StatefulWidget {
  const DailyLogScreen({super.key, required this.staff, required this.month});
  final Json staff;
  final String month;
  @override
  State<DailyLogScreen> createState() => _DailyLogScreenState();
}

class _DailyLogScreenState extends State<DailyLogScreen> {
  final Map<String, TextEditingController> _hours = {}, _words = {};
  final Map<String, String> _amount = {};
  late final List<DateTime> _days;
  bool _loading = true, _busy = false;

  @override
  void initState() {
    super.initState();
    final parts = widget.month.split('-').map(int.parse).toList();
    final last = DateTime(parts[0], parts[1] + 1, 0).day;
    _days = [for (var d = 1; d <= last; d++) DateTime(parts[0], parts[1], d)];
    for (final d in _days) {
      final key = _key(d);
      _hours[key] = TextEditingController();
      _words[key] = TextEditingController();
    }
    _load();
  }

  @override
  void dispose() {
    for (final c in [..._hours.values, ..._words.values]) {
      c.dispose();
    }
    super.dispose();
  }

  String _key(DateTime d) => DateFormat('yyyy-MM-dd').format(d);

  Future<void> _load() async {
    try {
      final res = await api.get('/payroll/staff/${widget.staff['id']}/daily/?month=${widget.month}');
      for (final d in (res['days'] as List)) {
        final key = d['date'] as String;
        _hours[key]?.text = d['hours'] == null ? '' : '${d['hours']}'.replaceAll(RegExp(r'\.00$'), '');
        _words[key]?.text = d['words'] == null ? '' : '${d['words']}';
        _amount[key] = d['amount'].toString();
      }
      if (mounted) setState(() => _loading = false);
    } catch (e) {
      if (mounted) {
        setState(() => _loading = false);
        toast(context, e);
      }
    }
  }

  Future<void> _save() async {
    FocusScope.of(context).unfocus();
    setState(() => _busy = true);
    try {
      final days = [
        for (final d in _days)
          if (_hours[_key(d)]!.text.trim().isNotEmpty || _words[_key(d)]!.text.trim().isNotEmpty)
            {
              'date': _key(d),
              'hours': _hours[_key(d)]!.text.trim().isEmpty ? null : _hours[_key(d)]!.text.trim(),
              'words': _words[_key(d)]!.text.trim().isEmpty ? null : int.tryParse(_words[_key(d)]!.text.trim()),
            },
      ];
      await api.send('PUT', '/payroll/staff/${widget.staff['id']}/daily/?month=${widget.month}', {'days': days});
      await _load();
      if (mounted) toast(context, 'Daily log saved');
    } catch (e) {
      if (mounted) toast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    num hoursTotal = 0, wordsTotal = 0;
    for (final d in _days) {
      hoursTotal += num.tryParse(_hours[_key(d)]!.text) ?? 0;
      wordsTotal += num.tryParse(_words[_key(d)]!.text) ?? 0;
    }
    return Scaffold(
      appBar: AppBar(title: Text('Daily log · ${monthLabel(widget.month)}'), actions: [TextButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Save'))]),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(children: [
              Container(
                width: double.infinity,
                color: scheme.primaryContainer,
                padding: const EdgeInsets.all(12),
                child: Text('${displayName(widget.staff)} · ${count(hoursTotal)} hours · ${count(wordsTotal)} words', textAlign: TextAlign.center, style: TextStyle(color: scheme.onPrimaryContainer, fontWeight: FontWeight.w600)),
              ),
              Expanded(
                child: ListView.separated(
                  keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
                  itemCount: _days.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final d = _days[i];
                    final key = _key(d);
                    final weekend = d.weekday == DateTime.saturday;
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(children: [
                        SizedBox(
                          width: 64,
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(DateFormat('d MMM').format(d), style: const TextStyle(fontWeight: FontWeight.w700)),
                            Text(DateFormat('EEE').format(d), style: TextStyle(fontSize: 11, color: weekend ? Colors.red : null)),
                          ]),
                        ),
                        Expanded(child: _cell(_hours[key]!, 'hours', decimal: true)),
                        const SizedBox(width: 8),
                        Expanded(child: _cell(_words[key]!, 'words')),
                        SizedBox(width: 70, child: Text(_amount[key] == null ? '' : npr(_amount[key]).replaceFirst('NPR ', ''), textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12))),
                      ]),
                    );
                  },
                ),
              ),
            ]),
    );
  }

  Widget _cell(TextEditingController c, String hint, {bool decimal = false}) => TextField(
        controller: c,
        onChanged: (_) => setState(() {}),
        keyboardType: TextInputType.numberWithOptions(decimal: decimal),
        decoration: InputDecoration(hintText: hint, isDense: true, border: const OutlineInputBorder()),
      );
}
