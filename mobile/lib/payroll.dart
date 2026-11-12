import 'package:intl/intl.dart';

import 'api.dart';

/// Same rule as the website: Super Admins, and content-unit roles with the manage_payroll capability.
bool canManagePayroll(Json? me) {
  if (me == null) return false;
  if (me['is_super_admin'] == true) return true;
  final caps = (me['capabilities'] as List?)?.map((e) => e.toString()).toList() ?? [];
  return me['unit']?['code'] == 'content' && caps.contains('manage_payroll');
}

final _number = NumberFormat.decimalPattern('en_IN');

String npr(dynamic value) {
  if (value == null || value == '') return '—';
  final n = num.tryParse(value.toString());
  if (n == null) return '—';
  return 'NPR ${_number.format(n)}';
}

String count(dynamic value) {
  final n = num.tryParse((value ?? 0).toString()) ?? 0;
  return _number.format(n);
}

String currentMonth() => DateFormat('yyyy-MM').format(DateTime.now());

String shiftMonth(String month, int delta) {
  final parts = month.split('-').map(int.parse).toList();
  return DateFormat('yyyy-MM').format(DateTime(parts[0], parts[1] + delta, 1));
}

String monthLabel(String month) {
  final parts = month.split('-').map(int.parse).toList();
  return DateFormat('MMMM yyyy').format(DateTime(parts[0], parts[1], 1));
}
