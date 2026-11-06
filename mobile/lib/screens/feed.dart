import 'dart:io';

import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../util.dart';
import '../widgets/api_image.dart';
import 'story_viewer.dart';

class FeedScreen extends StatefulWidget {
  const FeedScreen({super.key});
  @override
  State<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends State<FeedScreen> {
  final _scroll = ScrollController();
  List<Json> _posts = [];
  List<Json> _stories = [];
  bool _loading = true, _more = false, _loadingMore = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_more && !_loadingMore && _scroll.position.extentAfter < 400) _loadMore();
    });
    _load();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final posts = await api.get('/feed/posts/');
      final stories = await api.get('/feed/stories/');
      if (!mounted) return;
      setState(() {
        _posts = (posts['results'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
        _more = posts['has_more'] == true;
        _stories = (stories['results'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
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

  Future<void> _loadMore() async {
    _loadingMore = true;
    try {
      final res = await api.get('/feed/posts/?before=${_posts.last['id']}');
      if (!mounted) return;
      setState(() {
        _posts.addAll((res['results'] as List).map((e) => Map<String, dynamic>.from(e)));
        _more = res['has_more'] == true;
      });
    } catch (_) {
    } finally {
      _loadingMore = false;
    }
  }

  Future<void> _newPost() async {
    final posted = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const NewPostScreen()));
    if (posted == true) _load();
  }

  Future<void> _addStory() async {
    final picked = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 85, maxWidth: 1600);
    if (picked == null || !mounted) return;
    final caption = await showDialog<String>(
      context: context,
      builder: (context) {
        final c = TextEditingController();
        return AlertDialog(
          title: const Text('Add to your story'),
          content: TextField(controller: c, maxLength: 200, decoration: const InputDecoration(hintText: 'Caption (optional)')),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, c.text), child: const Text('Share')),
          ],
        );
      },
    );
    if (caption == null) return;
    try {
      await api.post('/feed/stories/', FormData.fromMap({
        'image': await MultipartFile.fromFile(picked.path, filename: picked.name),
        'caption': caption,
      }));
      _load();
    } catch (e) {
      if (mounted) toast(context, e);
    }
  }

  void _openStories(int index) async {
    await Navigator.push(context, MaterialPageRoute(fullscreenDialog: true, builder: (_) => StoryViewer(groups: _stories, start: index)));
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final me = context.watch<AppState>().me!;
    final mine = _stories.indexWhere((g) => g['user']['id'] == me['id']);
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(onPressed: _newPost, icon: const Icon(Icons.edit), label: const Text('Post')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView.builder(
                controller: _scroll,
                padding: const EdgeInsets.only(bottom: 90),
                itemCount: _posts.length + 2,
                itemBuilder: (context, i) {
                  if (i == 0) return _storyBar(me, mine);
                  if (i == 1) {
                    if (_error != null) return Padding(padding: const EdgeInsets.all(24), child: Text(_error!));
                    if (_posts.isEmpty) return const Padding(padding: EdgeInsets.all(48), child: Center(child: Text('No posts yet. Be the first!')));
                    return const SizedBox.shrink();
                  }
                  return PostCard(
                    key: ValueKey(_posts[i - 2]['id']),
                    post: _posts[i - 2],
                    meId: me['id'].toString(),
                    onDeleted: () => setState(() => _posts.removeAt(i - 2)),
                  );
                },
              ),
      ),
    );
  }

  Widget _storyBar(Json me, int mine) {
    final others = [for (var i = 0; i < _stories.length; i++) if (i != mine) i];
    return SizedBox(
      height: 104,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        children: [
          _StoryBubble(
            person: Map<String, dynamic>.from(me),
            label: 'Your story',
            ring: mine >= 0 ? (_stories[mine]['all_seen'] == true ? Colors.grey : Theme.of(context).colorScheme.primary) : null,
            plus: true,
            onTap: mine >= 0 ? () => _openStories(mine) : _addStory,
            onPlus: _addStory,
          ),
          for (final i in others)
            _StoryBubble(
              person: Map<String, dynamic>.from(_stories[i]['user']),
              label: displayName(_stories[i]['user']).split(' ').first,
              ring: _stories[i]['all_seen'] == true ? Colors.grey : Theme.of(context).colorScheme.primary,
              onTap: () => _openStories(i),
            ),
        ],
      ),
    );
  }
}

class _StoryBubble extends StatelessWidget {
  const _StoryBubble({required this.person, required this.label, required this.onTap, this.ring, this.plus = false, this.onPlus});
  final Json person;
  final String label;
  final Color? ring;
  final bool plus;
  final VoidCallback onTap;
  final VoidCallback? onPlus;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 12),
      child: GestureDetector(
        onTap: onTap,
        child: SizedBox(
          width: 64,
          child: Column(children: [
            Stack(clipBehavior: Clip.none, children: [
              Container(
                padding: const EdgeInsets.all(2.5),
                decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: ring ?? Colors.transparent, width: 2.5)),
                child: Avatar(person, radius: 24),
              ),
              if (plus)
                Positioned(
                  right: -2,
                  bottom: -2,
                  child: GestureDetector(
                    onTap: onPlus,
                    child: CircleAvatar(radius: 10, backgroundColor: Theme.of(context).colorScheme.primary, child: const Icon(Icons.add, size: 14, color: Colors.white)),
                  ),
                ),
            ]),
            const SizedBox(height: 4),
            Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11)),
          ]),
        ),
      ),
    );
  }
}

class PostCard extends StatefulWidget {
  const PostCard({super.key, required this.post, required this.meId, required this.onDeleted});
  final Json post;
  final String meId;
  final VoidCallback onDeleted;
  @override
  State<PostCard> createState() => _PostCardState();
}

class _PostCardState extends State<PostCard> {
  late Json post = widget.post;

  Future<void> _like() async {
    final liked = post['liked'] == true;
    setState(() => post = {...post, 'liked': !liked, 'like_count': (post['like_count'] as int) + (liked ? -1 : 1)});
    try {
      final res = liked ? await api.delete('/feed/posts/${post['id']}/like/') : await api.post('/feed/posts/${post['id']}/like/');
      if (res != null && mounted) setState(() => post = res);
    } catch (e) {
      if (mounted) {
        setState(() => post = widget.post);
        toast(context, e);
      }
    }
  }

  Future<void> _delete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete this post?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await api.delete('/feed/posts/${post['id']}/');
      widget.onDeleted();
    } catch (e) {
      if (mounted) toast(context, e);
    }
  }

  void _comments() async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => CommentsSheet(postId: post['id'].toString(), onAdded: () => setState(() => post = {...post, 'comment_count': (post['comment_count'] as int) + 1})),
    );
  }

  @override
  Widget build(BuildContext context) {
    final author = Map<String, dynamic>.from(post['author']);
    final liked = post['liked'] == true;
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      clipBehavior: Clip.antiAlias,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        ListTile(
          leading: Avatar(author),
          title: Text(displayName(author), style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text('${author['role'] ?? ''} · ${timeAgo(post['created_at'])}'),
          trailing: author['id'].toString() == widget.meId ? IconButton(icon: const Icon(Icons.delete_outline), onPressed: _delete) : null,
        ),
        if ((post['body'] as String).isNotEmpty) Padding(padding: const EdgeInsets.fromLTRB(16, 0, 16, 12), child: Text(post['body'])),
        if (post['image'] != null) ConstrainedBox(constraints: const BoxConstraints(maxHeight: 420), child: SizedBox(width: double.infinity, child: ApiImage(post['image']))),
        Row(children: [
          TextButton.icon(
            onPressed: _like,
            icon: Icon(liked ? Icons.favorite : Icons.favorite_border, color: liked ? Colors.red : null),
            label: Text('${post['like_count']}'),
          ),
          TextButton.icon(onPressed: _comments, icon: const Icon(Icons.mode_comment_outlined), label: Text('${post['comment_count']}')),
        ]),
      ]),
    );
  }
}

class CommentsSheet extends StatefulWidget {
  const CommentsSheet({super.key, required this.postId, required this.onAdded});
  final String postId;
  final VoidCallback onAdded;
  @override
  State<CommentsSheet> createState() => _CommentsSheetState();
}

class _CommentsSheetState extends State<CommentsSheet> {
  final _text = TextEditingController();
  List<Json> _comments = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await api.get('/feed/posts/${widget.postId}/comments/');
      if (mounted) setState(() {
        _comments = (res['results'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _send() async {
    final body = _text.text.trim();
    if (body.isEmpty) return;
    _text.clear();
    try {
      final c = await api.post('/feed/posts/${widget.postId}/comments/', {'body': body});
      widget.onAdded();
      if (mounted) setState(() => _comments.add(c!));
    } catch (e) {
      if (mounted) toast(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.6,
        child: Column(children: [
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _comments.isEmpty
                    ? const Center(child: Text('No comments yet'))
                    : ListView(children: [
                        for (final c in _comments)
                          ListTile(
                            leading: Avatar(c['author'], radius: 16),
                            title: Text(displayName(c['author']), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                            subtitle: Text(c['body']),
                            trailing: Text(timeAgo(c['created_at']), style: const TextStyle(fontSize: 11)),
                          ),
                      ]),
          ),
          Padding(
            padding: const EdgeInsets.all(8),
            child: Row(children: [
              Expanded(child: TextField(controller: _text, onSubmitted: (_) => _send(), decoration: const InputDecoration(hintText: 'Write a comment…', border: OutlineInputBorder(), isDense: true))),
              IconButton(onPressed: _send, icon: const Icon(Icons.send)),
            ]),
          ),
        ]),
      ),
    );
  }
}

class NewPostScreen extends StatefulWidget {
  const NewPostScreen({super.key});
  @override
  State<NewPostScreen> createState() => _NewPostScreenState();
}

class _NewPostScreenState extends State<NewPostScreen> {
  final _text = TextEditingController();
  XFile? _photo;
  bool _busy = false;

  Future<void> _pick(ImageSource source) async {
    final f = await ImagePicker().pickImage(source: source, imageQuality: 85, maxWidth: 1600);
    if (f != null) setState(() => _photo = f);
  }

  Future<void> _post() async {
    setState(() => _busy = true);
    try {
      await api.post('/feed/posts/', FormData.fromMap({
        'body': _text.text,
        if (_photo != null) 'image': await MultipartFile.fromFile(_photo!.path, filename: _photo!.name),
      }));
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
    return Scaffold(
      appBar: AppBar(title: const Text('New post'), actions: [
        TextButton(onPressed: _busy ? null : _post, child: Text(_busy ? 'Posting…' : 'Post')),
      ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(controller: _text, maxLines: 6, maxLength: 4000, decoration: const InputDecoration(hintText: "What's happening?", border: OutlineInputBorder())),
        if (_photo != null)
          Stack(children: [
            ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.file(File(_photo!.path))),
            Positioned(right: 4, top: 4, child: IconButton.filledTonal(icon: const Icon(Icons.close), onPressed: () => setState(() => _photo = null))),
          ]),
        const SizedBox(height: 12),
        Row(children: [
          OutlinedButton.icon(onPressed: () => _pick(ImageSource.gallery), icon: const Icon(Icons.photo_outlined), label: const Text('Photo')),
          const SizedBox(width: 8),
          OutlinedButton.icon(onPressed: () => _pick(ImageSource.camera), icon: const Icon(Icons.camera_alt_outlined), label: const Text('Camera')),
        ]),
      ]),
    );
  }
}
