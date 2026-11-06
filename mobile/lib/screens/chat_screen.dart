import 'dart:async';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import '../api.dart';
import '../call.dart';
import '../state.dart';
import '../util.dart';
import '../widgets/api_image.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, required this.convKey, required this.title, this.peer, this.group});
  final String convKey, title;
  final Json? peer, group;
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _text = TextEditingController();
  final _scroll = ScrollController();
  final _recorder = AudioRecorder();
  List<Json> _messages = [];
  List<Json> _receipts = [];
  Timer? _timer, _recTimer;
  bool _loading = true, _recording = false, _fetching = false;
  int _recSeconds = 0;
  int _lastSeq = 0;

  String get _me => context.read<AppState>().me!['id'].toString();

  @override
  void initState() {
    super.initState();
    _fetch();
    _timer = Timer.periodic(const Duration(seconds: 2), (_) => _fetch());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _recTimer?.cancel();
    _recorder.dispose();
    _text.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _fetch() async {
    if (_fetching) return;
    _fetching = true;
    try {
      final res = await api.get('/chat/messages/?with=${widget.convKey}${_lastSeq > 0 ? '&after=$_lastSeq' : ''}');
      if (!mounted) return;
      final fresh = (res['messages'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
      final atBottom = !_scroll.hasClients || _scroll.position.extentAfter < 120;
      setState(() {
        if (_lastSeq == 0) {
          _messages = fresh;
        } else {
          final known = _messages.map((m) => m['id']).toSet();
          _messages.addAll(fresh.where((m) => !known.contains(m['id'])));
        }
        if (_messages.isNotEmpty) _lastSeq = _messages.map((m) => m['seq'] as int).reduce((a, b) => a > b ? a : b);
        _receipts = (res['receipts'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
        _loading = false;
      });
      if (fresh.isNotEmpty) {
        if (atBottom) WidgetsBinding.instance.addPostFrameCallback((_) => _toBottom());
        api.post('/chat/read/', {'with': widget.convKey, 'last_seq': _lastSeq}).then((_) {
          if (mounted) context.read<AppState>().refreshUnread();
        }).catchError((_) => null);
      }
    } catch (_) {
      if (mounted && _loading) setState(() => _loading = false);
    } finally {
      _fetching = false;
    }
  }

  void _toBottom() {
    if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
  }

  Future<void> _send({String? body, Map<String, dynamic>? extra}) async {
    try {
      final msg = extra == null
          ? await api.post('/chat/messages/', {'to': widget.convKey, 'body': body})
          : await api.post('/chat/messages/', FormData.fromMap({'to': widget.convKey, ...extra}));
      if (!mounted) return;
      setState(() {
        _messages.add(msg!);
        _lastSeq = msg['seq'] as int;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) => _toBottom());
    } catch (e) {
      if (mounted) toast(context, e);
    }
  }

  void _sendText() {
    final body = _text.text.trim();
    if (body.isEmpty) return;
    _text.clear();
    _send(body: body);
  }

  Future<void> _attach() async {
    final choice = await showModalBottomSheet<String>(
      context: context,
      builder: (context) => SafeArea(
        child: Wrap(children: [
          ListTile(leading: const Icon(Icons.photo_outlined), title: const Text('Photo'), onTap: () => Navigator.pop(context, 'photo')),
          ListTile(leading: const Icon(Icons.camera_alt_outlined), title: const Text('Camera'), onTap: () => Navigator.pop(context, 'camera')),
          ListTile(leading: const Icon(Icons.insert_drive_file_outlined), title: const Text('File'), onTap: () => Navigator.pop(context, 'file')),
        ]),
      ),
    );
    if (choice == null) return;
    String? path, name;
    if (choice == 'file') {
      final r = await FilePicker.pickFiles();
      final f = r.isEmpty ? null : r.first;
      path = f?.path;
      name = f?.name;
    } else {
      final f = await ImagePicker().pickImage(source: choice == 'camera' ? ImageSource.camera : ImageSource.gallery, imageQuality: 85, maxWidth: 1600);
      path = f?.path;
      name = f?.name;
    }
    if (path == null) return;
    await _send(extra: {'file': await MultipartFile.fromFile(path, filename: name)});
  }

  Future<void> _toggleRecord() async {
    if (_recording) {
      final path = await _recorder.stop();
      _recTimer?.cancel();
      final seconds = _recSeconds;
      setState(() => _recording = false);
      if (path != null && seconds >= 1) {
        await _send(extra: {'audio': await MultipartFile.fromFile(path, filename: 'voice.m4a'), 'duration': seconds.toString()});
      }
      return;
    }
    if (!(await Permission.microphone.request()).isGranted) {
      if (mounted) toast(context, 'Allow microphone access to record voice messages.');
      return;
    }
    final dir = await getTemporaryDirectory();
    await _recorder.start(const RecordConfig(encoder: AudioEncoder.aacLc), path: '${dir.path}/voice_${DateTime.now().millisecondsSinceEpoch}.m4a');
    _recSeconds = 0;
    _recTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      setState(() => _recSeconds++);
      if (_recSeconds >= 300) _toggleRecord();
    });
    setState(() => _recording = true);
  }

  /// ✓ sent, ✓✓ delivered, blue ✓✓ seen (by everyone else in the conversation).
  Widget _ticks(Json m) {
    if (m['sender'].toString() != _me) return const SizedBox.shrink();
    final seq = m['seq'] as int;
    final others = _receipts;
    final seen = others.isNotEmpty && others.every((r) => (r['read_up_to'] as int) >= seq);
    final delivered = others.isNotEmpty && others.every((r) => (r['delivered_up_to'] as int) >= seq);
    return Icon(delivered || seen ? Icons.done_all : Icons.done, size: 14, color: seen ? Colors.lightBlueAccent : Colors.white70);
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final peer = widget.peer;
    final online = peer != null && state.isOnline(peer['id']);
    final names = {for (final r in _receipts) r['id'].toString(): r['name']};
    return Scaffold(
      appBar: AppBar(
        title: Row(children: [
          if (peer != null) ...[Avatar(peer, radius: 16, online: online), const SizedBox(width: 10)],
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(widget.title, style: const TextStyle(fontSize: 17)),
            if (peer != null) Text(online ? 'online' : 'offline', style: TextStyle(fontSize: 11, color: online ? Colors.green : Colors.grey)),
          ])),
        ]),
        actions: [
          if (peer != null) IconButton(icon: const Icon(Icons.call), tooltip: 'Audio call', onPressed: () => context.read<CallController>().start(peer)),
        ],
      ),
      body: Column(children: [
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _messages.isEmpty
                  ? const Center(child: Text('No messages yet. Say hello!'))
                  : ListView.builder(
                      controller: _scroll,
                      padding: const EdgeInsets.all(12),
                      itemCount: _messages.length,
                      itemBuilder: (context, i) {
                        final m = _messages[i];
                        final mine = m['sender'].toString() == _me;
                        return _Bubble(
                          message: m,
                          mine: mine,
                          sender: widget.peer == null && !mine ? names[m['sender'].toString()]?.toString() : null,
                          ticks: _ticks(m),
                        );
                      },
                    ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
            child: _recording
                ? Row(children: [
                    const Icon(Icons.fiber_manual_record, color: Colors.red),
                    const SizedBox(width: 8),
                    Expanded(child: Text('Recording… ${mmss(_recSeconds)}')),
                    IconButton.filled(onPressed: _toggleRecord, icon: const Icon(Icons.send)),
                  ])
                : Row(children: [
                    IconButton(onPressed: _attach, icon: const Icon(Icons.attach_file)),
                    Expanded(
                      child: TextField(
                        controller: _text,
                        minLines: 1,
                        maxLines: 4,
                        onChanged: (_) => setState(() {}),
                        textCapitalization: TextCapitalization.sentences,
                        decoration: InputDecoration(hintText: 'Message', border: OutlineInputBorder(borderRadius: BorderRadius.circular(24)), isDense: true),
                      ),
                    ),
                    const SizedBox(width: 4),
                    _text.text.trim().isEmpty
                        ? IconButton.filledTonal(onPressed: _toggleRecord, icon: const Icon(Icons.mic))
                        : IconButton.filled(onPressed: _sendText, icon: const Icon(Icons.send)),
                  ]),
          ),
        ),
      ]),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.message, required this.mine, required this.ticks, this.sender});
  final Json message;
  final bool mine;
  final Widget ticks;
  final String? sender;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = mine ? scheme.primary : scheme.surfaceContainerHighest;
    final fg = mine ? scheme.onPrimary : scheme.onSurface;
    final file = message['file'] as Map?;
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        margin: const EdgeInsets.symmetric(vertical: 3),
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 6),
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(16)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          if (sender != null) Text(sender!, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: fg.withValues(alpha: 0.8))),
          if (message['audio'] != null) VoicePlayer(path: message['audio'], seconds: message['audio_duration'] ?? 0, color: fg),
          if (file != null && file['is_image'] == true)
            GestureDetector(
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => Scaffold(appBar: AppBar(), backgroundColor: Colors.black, body: Center(child: InteractiveViewer(child: ApiImage(file['url'], fit: BoxFit.contain)))))),
              child: ClipRRect(borderRadius: BorderRadius.circular(8), child: ApiImage(file['url'], height: 200)),
            ),
          if (file != null && file['is_image'] != true)
            InkWell(
              onTap: () async {
                try {
                  final f = await api.download('${file['url']}?download=1', file['name']);
                  await OpenFilex.open(f.path);
                } catch (e) {
                  if (context.mounted) toast(context, e);
                }
              },
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.insert_drive_file_outlined, color: fg),
                const SizedBox(width: 6),
                Flexible(child: Text(file['name'], style: TextStyle(color: fg, decoration: TextDecoration.underline))),
              ]),
            ),
          if ((message['body'] as String).isNotEmpty) Text(message['body'], style: TextStyle(color: fg, fontSize: 15)),
          const SizedBox(height: 2),
          Row(mainAxisSize: MainAxisSize.min, mainAxisAlignment: MainAxisAlignment.end, children: [
            Text(clock(message['created_at']), style: TextStyle(fontSize: 10, color: fg.withValues(alpha: 0.7))),
            const SizedBox(width: 4),
            ticks,
          ]),
        ]),
      ),
    );
  }
}

class VoicePlayer extends StatefulWidget {
  const VoicePlayer({super.key, required this.path, required this.seconds, required this.color});
  final String path;
  final int seconds;
  final Color color;
  @override
  State<VoicePlayer> createState() => _VoicePlayerState();
}

class _VoicePlayerState extends State<VoicePlayer> {
  final _player = AudioPlayer();
  bool _playing = false, _loading = false;
  Duration _pos = Duration.zero;

  @override
  void initState() {
    super.initState();
    _player.onPlayerComplete.listen((_) => setState(() {
          _playing = false;
          _pos = Duration.zero;
        }));
    _player.onPositionChanged.listen((p) => setState(() => _pos = p));
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    if (_playing) {
      await _player.pause();
      setState(() => _playing = false);
      return;
    }
    setState(() => _loading = true);
    try {
      if (_player.source == null) {
        final File f = await api.download(widget.path, 'voice_${widget.path.hashCode}.m4a');
        await _player.setSource(DeviceFileSource(f.path));
      }
      await _player.resume();
      setState(() => _playing = true);
    } catch (e) {
      if (mounted) toast(context, 'Could not play the voice message.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final total = widget.seconds <= 0 ? 1 : widget.seconds;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      _loading
          ? const SizedBox(width: 32, height: 32, child: Padding(padding: EdgeInsets.all(6), child: CircularProgressIndicator(strokeWidth: 2)))
          : IconButton(onPressed: _toggle, icon: Icon(_playing ? Icons.pause_circle : Icons.play_circle, color: widget.color, size: 32), padding: EdgeInsets.zero, constraints: const BoxConstraints(minWidth: 32, minHeight: 32)),
      SizedBox(width: 120, child: LinearProgressIndicator(value: (_pos.inSeconds / total).clamp(0.0, 1.0), color: widget.color, backgroundColor: widget.color.withValues(alpha: 0.3))),
      const SizedBox(width: 8),
      Text(mmss(widget.seconds), style: TextStyle(color: widget.color, fontSize: 12)),
    ]);
  }
}
