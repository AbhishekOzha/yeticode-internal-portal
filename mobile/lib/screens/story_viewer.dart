import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../util.dart';
import '../widgets/api_image.dart';

/// Full-screen stories: tap right/left to move, they advance by themselves every 5 seconds.
class StoryViewer extends StatefulWidget {
  const StoryViewer({super.key, required this.groups, required this.start});
  final List<Json> groups;
  final int start;
  @override
  State<StoryViewer> createState() => _StoryViewerState();
}

class _StoryViewerState extends State<StoryViewer> with SingleTickerProviderStateMixin {
  late int _group = widget.start;
  int _index = 0;
  late final AnimationController _progress = AnimationController(vsync: this, duration: const Duration(seconds: 5))
    ..addStatusListener((s) {
      if (s == AnimationStatus.completed) _next();
    });

  Json get _g => widget.groups[_group];
  List get _stories => _g['stories'] as List;
  Json get _story => Map<String, dynamic>.from(_stories[_index]);

  @override
  void initState() {
    super.initState();
    _show();
  }

  @override
  void dispose() {
    _progress.dispose();
    super.dispose();
  }

  void _show() {
    _progress.forward(from: 0);
    final mine = _g['user']['id'].toString() == context.read<AppState>().me!['id'].toString();
    if (!mine) api.post('/feed/stories/${_story['id']}/viewed/').catchError((_) => null);
    _stories[_index]['seen'] = true;
    setState(() {});
  }

  void _next() {
    if (_index < _stories.length - 1) {
      _index++;
    } else if (_group < widget.groups.length - 1) {
      _group++;
      _index = 0;
    } else {
      Navigator.pop(context);
      return;
    }
    _show();
  }

  void _prev() {
    if (_index > 0) {
      _index--;
    } else if (_group > 0) {
      _group--;
      _index = widget.groups[_group]['stories'].length - 1;
    }
    _show();
  }

  Future<void> _delete() async {
    _progress.stop();
    try {
      await api.delete('/feed/stories/${_story['id']}/');
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) toast(context, e);
    }
  }

  Future<void> _viewers() async {
    _progress.stop();
    try {
      final res = await api.get('/feed/stories/${_story['id']}/viewed/');
      if (!mounted) return;
      final people = (res['results'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
      await showModalBottomSheet(
        context: context,
        builder: (_) => ListView(children: [
          ListTile(title: Text('Seen by ${people.length}')),
          for (final p in people) ListTile(leading: Avatar(p, radius: 16), title: Text(displayName(p))),
        ]),
      );
    } catch (_) {}
    if (mounted) _progress.forward();
  }

  @override
  Widget build(BuildContext context) {
    final user = Map<String, dynamic>.from(_g['user']);
    final mine = user['id'].toString() == context.read<AppState>().me!['id'].toString();
    return Scaffold(
      backgroundColor: Colors.black,
      body: GestureDetector(
        onTapUp: (d) => d.localPosition.dx < MediaQuery.of(context).size.width / 3 ? _prev() : _next(),
        onLongPressStart: (_) => _progress.stop(),
        onLongPressEnd: (_) => _progress.forward(),
        onVerticalDragEnd: (d) {
          if ((d.primaryVelocity ?? 0) > 300) Navigator.pop(context);
        },
        child: Stack(children: [
          Positioned.fill(child: ApiImage(_story['image'], fit: BoxFit.contain)),
          SafeArea(
            child: Column(children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
                child: Row(children: [
                  for (var i = 0; i < _stories.length; i++)
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 2),
                        child: i == _index
                            ? AnimatedBuilder(animation: _progress, builder: (_, __) => LinearProgressIndicator(value: _progress.value, minHeight: 3, backgroundColor: Colors.white30, color: Colors.white))
                            : LinearProgressIndicator(value: i < _index ? 1 : 0, minHeight: 3, backgroundColor: Colors.white30, color: Colors.white),
                      ),
                    ),
                ]),
              ),
              ListTile(
                leading: Avatar(user, radius: 18),
                title: Text(mine ? 'Your story' : displayName(user), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                subtitle: Text(timeAgo(_story['created_at']), style: const TextStyle(color: Colors.white70)),
                trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                  if (mine) IconButton(icon: const Icon(Icons.delete_outline, color: Colors.white), onPressed: _delete),
                  IconButton(icon: const Icon(Icons.close, color: Colors.white), onPressed: () => Navigator.pop(context)),
                ]),
              ),
              const Spacer(),
              if ((_story['caption'] as String).isNotEmpty)
                Container(
                  width: double.infinity,
                  color: Colors.black54,
                  padding: const EdgeInsets.all(16),
                  child: Text(_story['caption'], textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 16)),
                ),
              if (mine) TextButton.icon(onPressed: _viewers, icon: const Icon(Icons.visibility_outlined, color: Colors.white), label: const Text('Seen by', style: TextStyle(color: Colors.white))),
            ]),
          ),
        ]),
      ),
    );
  }
}
