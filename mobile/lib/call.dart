import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';

import 'api.dart';
import 'state.dart';
import 'util.dart';
import 'widgets/api_image.dart';

const _finished = ['ended', 'missed', 'declined', 'cancelled'];
const _endText = {'ended': 'Call ended', 'missed': 'No answer', 'declined': 'Call declined', 'cancelled': 'Call cancelled'};

/// One-to-one audio calls. The audio goes straight between the two apps over WebRTC; the server
/// only rings and passes the set-up messages, exactly like the website. Phones can watch a
/// shared screen from a computer but can't share their own.
class CallController extends ChangeNotifier {
  CallController(this._app) {
    _sub = _app.incomingCalls.listen(_onIncoming);
  }

  final AppState _app;
  late final StreamSubscription _sub;

  Json? call; // id, peer, incoming, status, phase
  bool muted = false;
  bool speaker = false;
  bool peerSharing = false;
  int elapsed = 0;
  String? notice;

  final remoteVideo = RTCVideoRenderer();
  bool _rendererReady = false;
  RTCPeerConnection? _pc;
  MediaStream? _local;
  int _afterSeq = 0;
  bool _offered = false;
  DateTime? _connectedAt;
  final _pending = <RTCIceCandidate>[];
  List<Map<String, dynamic>>? _ice;
  Timer? _poll, _timer, _ring;
  final _dismissed = <String>{};

  bool get active => call != null;

  Future<void> _ensureRenderer() async {
    if (_rendererReady) return;
    await remoteVideo.initialize();
    _rendererReady = true;
  }

  void _onIncoming(Json? incoming) {
    if (incoming == null) {
      if (call?['incoming'] == true && call?['status'] == 'ringing') _finish('missed', 'Missed call');
      return;
    }
    if (call != null || _dismissed.contains(incoming['id'])) return;
    call = {'id': incoming['id'], 'peer': incoming['peer'], 'incoming': true, 'status': 'ringing', 'phase': 'ringing'};
    _startRing();
    _poll = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
    notifyListeners();
  }

  Future<void> start(Json peer) async {
    if (call != null) return;
    if (!await _micOk()) return;
    try {
      final started = await api.post('/calls/', {'to': peer['id'].toString()});
      call = {'id': started!['id'], 'peer': started['peer'], 'incoming': false, 'status': 'ringing', 'phase': 'calling'};
      _startRing();
      _poll = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
      notifyListeners();
    } on ApiError catch (e) {
      _notice(e.message);
    }
  }

  Future<bool> _micOk() async {
    final status = await Permission.microphone.request();
    if (!status.isGranted) {
      _notice('Allow microphone access to make calls.');
      return false;
    }
    return true;
  }

  void _notice(String text) {
    notice = text;
    notifyListeners();
    Timer(const Duration(seconds: 3), () {
      if (notice == text) {
        notice = null;
        notifyListeners();
      }
    });
  }

  void _startRing() {
    _ring?.cancel();
    _ring = Timer.periodic(const Duration(milliseconds: 1500), (_) {
      if (call?['status'] == 'ringing') {
        SystemSound.play(SystemSoundType.alert);
        HapticFeedback.heavyImpact();
      }
    });
  }

  Future<RTCPeerConnection> _connect(String id, {bool offerer = false}) async {
    await _ensureRenderer();
    _ice ??= ((await api.get('/calls/config/'))['ice_servers'] as List).cast<Map<String, dynamic>>();
    _local = await navigator.mediaDevices.getUserMedia({'audio': true, 'video': false});
    final pc = await createPeerConnection({'iceServers': _ice});
    _pc = pc;
    for (final track in _local!.getTracks()) {
      await pc.addTrack(track, _local!);
    }
    if (offerer) {
      await pc.addTransceiver(
        kind: RTCRtpMediaType.RTCRtpMediaTypeVideo,
        init: RTCRtpTransceiverInit(direction: TransceiverDirection.SendRecv),
      );
    }
    pc.onIceCandidate = (c) {
      if (c.candidate != null) api.post('/calls/$id/signal/', {'kind': 'candidate', 'data': c.toMap()}).catchError((_) => null);
    };
    pc.onTrack = (event) {
      if (event.track.kind == 'video' && event.streams.isNotEmpty) {
        remoteVideo.srcObject = event.streams.first;
        notifyListeners();
      }
    };
    pc.onConnectionState = (state) {
      if (state == RTCPeerConnectionState.RTCPeerConnectionStateConnected) {
        _connectedAt ??= DateTime.now();
        _ring?.cancel();
        call = {...?call, 'phase': 'connected'};
        _timer ??= Timer.periodic(const Duration(milliseconds: 500), (_) {
          elapsed = DateTime.now().difference(_connectedAt!).inSeconds;
          notifyListeners();
        });
        notifyListeners();
      } else if (state == RTCPeerConnectionState.RTCPeerConnectionStateFailed) {
        api.post('/calls/$id/end/').catchError((_) => null);
        _finish('ended', "Couldn't connect the call. The network may be blocking it.");
      }
    };
    return pc;
  }

  bool _ticking = false;
  Future<void> _tick() async {
    final current = call;
    if (current == null || _ticking) return;
    _ticking = true;
    final id = current['id'].toString();
    try {
      final res = await api.get('/calls/$id/?after=$_afterSeq');
      if (call == null || call!['id'].toString() != id) return;
      final status = res['call']['status'] as String;
      if (_finished.contains(status)) {
        _finish(status);
        return;
      }
      if (status == 'active' && current['incoming'] == false && !_offered) {
        _offered = true;
        call = {...call!, 'status': 'active', 'phase': 'connecting'};
        notifyListeners();
        final pc = await _connect(id, offerer: true);
        final offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        await api.post('/calls/$id/signal/', {'kind': 'offer', 'data': {'type': offer.type, 'sdp': offer.sdp}});
      }
      for (final signal in (res['signals'] as List)) {
        final s = Map<String, dynamic>.from(signal);
        _afterSeq = (s['seq'] as num).toInt() > _afterSeq ? (s['seq'] as num).toInt() : _afterSeq;
        await _apply(id, s);
      }
    } catch (_) {
      // Network hiccup: try again next tick.
    } finally {
      _ticking = false;
    }
  }

  Future<void> _apply(String id, Map<String, dynamic> signal) async {
    final pc = _pc;
    if (pc == null) return;
    final kind = signal['kind'];
    final data = Map<String, dynamic>.from(signal['data'] ?? {});
    if (kind == 'screen') {
      peerSharing = data['sharing'] == true;
      notifyListeners();
      return;
    }
    if (kind == 'candidate') {
      final candidate = RTCIceCandidate(data['candidate'], data['sdpMid'], data['sdpMLineIndex']);
      if (await pc.getRemoteDescription() != null) {
        await pc.addCandidate(candidate).catchError((_) => null);
      } else {
        _pending.add(candidate);
      }
      return;
    }
    if (kind == 'offer') {
      await pc.setRemoteDescription(RTCSessionDescription(data['sdp'], data['type']));
      final answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      await api.post('/calls/$id/signal/', {'kind': 'answer', 'data': {'type': answer.type, 'sdp': answer.sdp}});
    } else if (kind == 'answer') {
      await pc.setRemoteDescription(RTCSessionDescription(data['sdp'], data['type']));
    }
    for (final c in _pending.toList()) {
      await pc.addCandidate(c).catchError((_) => null);
    }
    _pending.clear();
  }

  Future<void> accept() async {
    final current = call;
    if (current == null) return;
    if (!await _micOk()) {
      decline();
      return;
    }
    final id = current['id'].toString();
    _dismissed.add(id);
    try {
      await _connect(id);
      await api.post('/calls/$id/accept/');
      _ring?.cancel();
      call = {...call!, 'status': 'active', 'phase': 'connecting'};
      notifyListeners();
    } catch (e) {
      api.post('/calls/$id/end/').catchError((_) => null);
      _finish('ended', 'Could not answer the call.');
    }
  }

  Future<void> decline() async {
    final id = call?['id'].toString();
    if (id == null) return;
    _dismissed.add(id);
    api.post('/calls/$id/decline/').catchError((_) => null);
    _finish('declined', false);
  }

  Future<void> hangUp() async {
    final current = call;
    if (current == null) return;
    final id = current['id'].toString();
    final ringingOut = current['status'] == 'ringing' && current['incoming'] == false;
    api.post('/calls/$id/end/').catchError((_) => null);
    _finish(ringingOut ? 'cancelled' : 'ended', false);
  }

  void toggleMute() {
    muted = !muted;
    for (final t in _local?.getAudioTracks() ?? <MediaStreamTrack>[]) {
      t.enabled = !muted;
    }
    notifyListeners();
  }

  void toggleSpeaker() {
    speaker = !speaker;
    Helper.setSpeakerphoneOn(speaker);
    notifyListeners();
  }

  /// text: null = the usual message for that status, false = none.
  void _finish(String status, [Object? text]) {
    _poll?.cancel();
    _timer?.cancel();
    _ring?.cancel();
    _poll = _timer = _ring = null;
    _pc?.close();
    _pc = null;
    _local?.getTracks().forEach((t) => t.stop());
    _local = null;
    if (_rendererReady) remoteVideo.srcObject = null;
    _pending.clear();
    _offered = false;
    _afterSeq = 0;
    _connectedAt = null;
    call = null;
    muted = false;
    speaker = false;
    peerSharing = false;
    elapsed = 0;
    final shown = text == null ? _endText[status] : (text == false ? null : text.toString());
    if (shown != null) _notice(shown);
    notifyListeners();
    _app.refreshUnread();
  }

  @override
  void dispose() {
    _sub.cancel();
    _poll?.cancel();
    _timer?.cancel();
    _ring?.cancel();
    remoteVideo.dispose();
    super.dispose();
  }
}

/// Sits above every screen: the incoming-call and in-call UI, and short notices.
class CallOverlay extends StatelessWidget {
  const CallOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.watch<CallController>();
    final call = c.call;
    return Stack(children: [
      if (c.notice != null && call == null)
        Positioned(
          left: 24,
          right: 24,
          bottom: 100,
          child: Material(
            color: Colors.black87,
            borderRadius: BorderRadius.circular(24),
            child: Padding(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12), child: Text(c.notice!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white))),
          ),
        ),
      if (call != null) Positioned.fill(child: _CallPanel(c, call)),
    ]);
  }
}

class _CallPanel extends StatelessWidget {
  const _CallPanel(this.c, this.call);
  final CallController c;
  final Json call;

  @override
  Widget build(BuildContext context) {
    final peer = Map<String, dynamic>.from(call['peer']);
    final incomingRinging = call['incoming'] == true && call['status'] == 'ringing';
    final connected = call['phase'] == 'connected';
    final label = incomingRinging
        ? 'Incoming audio call'
        : connected
            ? mmss(c.elapsed)
            : call['status'] == 'ringing'
                ? 'Calling…'
                : 'Connecting…';
    return Material(
      color: const Color(0xFF101828),
      child: SafeArea(
        child: Column(children: [
          if (c.peerSharing)
            Expanded(
              flex: 3,
              child: Container(
                margin: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(12)),
                clipBehavior: Clip.antiAlias,
                child: Stack(children: [
                  Positioned.fill(child: RTCVideoView(c.remoteVideo, objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitContain)),
                  Positioned(
                    left: 12,
                    top: 8,
                    child: Text('${displayName(peer)} is sharing their screen', style: const TextStyle(color: Colors.white, fontSize: 12)),
                  ),
                ]),
              ),
            ),
          Expanded(
            flex: 2,
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Avatar(peer, radius: c.peerSharing ? 28 : 56),
              const SizedBox(height: 16),
              Text(displayName(peer), style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              Text(label, style: const TextStyle(color: Colors.white70, fontSize: 16)),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.only(bottom: 48),
            child: incomingRinging
                ? Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
                    _Round(Icons.call_end, Colors.red, 'Decline', c.decline),
                    _Round(Icons.call, Colors.green, 'Accept', c.accept),
                  ])
                : Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
                    if (connected) _Round(c.muted ? Icons.mic_off : Icons.mic, c.muted ? Colors.white : Colors.white24, c.muted ? 'Unmute' : 'Mute', c.toggleMute, dark: c.muted),
                    _Round(Icons.call_end, Colors.red, 'End', c.hangUp),
                    if (connected) _Round(c.speaker ? Icons.volume_up : Icons.volume_down, c.speaker ? Colors.white : Colors.white24, 'Speaker', c.toggleSpeaker, dark: c.speaker),
                  ]),
          ),
        ]),
      ),
    );
  }
}

class _Round extends StatelessWidget {
  const _Round(this.icon, this.color, this.label, this.onTap, {this.dark = false});
  final IconData icon;
  final Color color;
  final String label;
  final VoidCallback onTap;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Column(mainAxisSize: MainAxisSize.min, children: [
      InkResponse(
        onTap: onTap,
        child: CircleAvatar(radius: 32, backgroundColor: color, child: Icon(icon, color: dark ? Colors.black : Colors.white, size: 30)),
      ),
      const SizedBox(height: 8),
      Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
    ]);
  }
}
