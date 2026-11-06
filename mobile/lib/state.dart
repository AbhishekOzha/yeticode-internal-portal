import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api.dart';

/// Who is signed in, plus the things the whole app watches: unread chats, who's online,
/// incoming calls and notifications. Polls the same endpoints the website does.
class AppState extends ChangeNotifier {
  Json? me;
  bool ready = false;
  Json branding = {};
  Map<String, int> unread = {};
  int totalUnread = 0;
  Map<String, dynamic> presence = {};
  int notificationsUnread = 0;
  Json? incomingCall;
  int latestSeq = 0;
  Timer? _chatTimer, _noteTimer;
  final _incomingController = StreamController<Json?>.broadcast();
  Stream<Json?> get incomingCalls => _incomingController.stream;

  bool get signedIn => me != null;
  bool get inTeam => me?['unit']?['code'] == 'content' && me?['is_super_admin'] != true;

  Future<void> start() async {
    try {
      branding = await api.branding();
    } catch (_) {}
    try {
      me = await api.session();
    } catch (_) {
      me = null;
    }
    ready = true;
    _poll();
    notifyListeners();
  }

  Future<void> signIn(String username, String password) async {
    final res = await api.login(username, password);
    me = (res['user'] ?? res) as Json;
    _poll();
    notifyListeners();
  }

  Future<void> signOut() async {
    try {
      await api.logout();
    } catch (_) {}
    me = null;
    _stop();
    notifyListeners();
  }

  void _stop() {
    _chatTimer?.cancel();
    _noteTimer?.cancel();
    unread = {};
    totalUnread = 0;
    notificationsUnread = 0;
    incomingCall = null;
  }

  void _poll() {
    _stop();
    if (me == null) return;
    _checkChat();
    _checkNotes();
    _chatTimer = Timer.periodic(const Duration(seconds: 2), (_) => _checkChat());
    _noteTimer = Timer.periodic(const Duration(seconds: 15), (_) => _checkNotes());
  }

  bool _busy = false;
  Future<void> _checkChat() async {
    if (me == null || _busy) return;
    _busy = true;
    try {
      final res = await api.get('/chat/updates/${latestSeq > 0 ? '?after=$latestSeq' : ''}');
      latestSeq = (res['latest_seq'] ?? latestSeq) as int;
      unread = Map<String, int>.from((res['unread'] as Map).map((k, v) => MapEntry(k.toString(), (v as num).toInt())));
      totalUnread = (res['total_unread'] ?? 0) as int;
      presence = Map<String, dynamic>.from(res['presence'] ?? {});
      final incoming = res['incoming_call'] as Json?;
      if (incoming?['id'] != incomingCall?['id']) {
        incomingCall = incoming;
        _incomingController.add(incoming);
      }
      notifyListeners();
    } on ApiError catch (e) {
      // Not in the team (403) or signed out (401/403): nothing to poll.
      if (e.status == 401) {
        me = null;
        _stop();
        notifyListeners();
      }
    } catch (_) {
    } finally {
      _busy = false;
    }
  }

  Future<void> _checkNotes() async {
    if (me == null) return;
    try {
      final res = await api.get('/notifications/');
      notificationsUnread = (res['unread'] ?? 0) as int;
      notifyListeners();
    } catch (_) {}
  }

  bool isOnline(Object id) => presence[id.toString()]?['online'] == true;

  void refreshUnread() => _checkChat();
  void refreshNotes() => _checkNotes();

  @override
  void dispose() {
    _stop();
    _incomingController.close();
    super.dispose();
  }
}
