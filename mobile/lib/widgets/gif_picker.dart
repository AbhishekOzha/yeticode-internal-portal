import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';

/// A GIF or sticker is sent as a normal message whose whole body is its Giphy address.
bool isGif(String? body) => RegExp(r'^https://media\d*\.giphy\.com/\S+\.(gif|webp)$', caseSensitive: false).hasMatch(body ?? '');

/// Search GIFs or stickers (free, through the server's Giphy key). Pops the chosen picture's address.
class GifPicker extends StatefulWidget {
  const GifPicker({super.key});
  @override
  State<GifPicker> createState() => _GifPickerState();
}

class _GifPickerState extends State<GifPicker> with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 2, vsync: this)..addListener(() {
      if (!_tabs.indexIsChanging) _search();
    });
  final _query = TextEditingController();
  Timer? _debounce;
  List<Json> _results = [];
  bool _loading = true;
  String? _error;

  String get _type => _tabs.index == 0 ? 'gifs' : 'stickers';

  @override
  void initState() {
    super.initState();
    _search();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await api.get('/chat/gifs/?type=$_type&q=${Uri.encodeQueryComponent(_query.text.trim())}');
      if (mounted) setState(() {
        _results = (res['results'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.6,
        child: Column(children: [
          TabBar(controller: _tabs, tabs: const [Tab(text: 'GIFs'), Tab(text: 'Stickers')]),
          Padding(
            padding: const EdgeInsets.all(8),
            child: TextField(
              controller: _query,
              onChanged: (_) {
                _debounce?.cancel();
                _debounce = Timer(const Duration(milliseconds: 400), _search);
              },
              decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search', border: OutlineInputBorder(), isDense: true),
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(_error!, textAlign: TextAlign.center)))
                    : _results.isEmpty
                        ? const Center(child: Text('Nothing found'))
                        : GridView.builder(
                            padding: const EdgeInsets.all(8),
                            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 3, mainAxisSpacing: 6, crossAxisSpacing: 6),
                            itemCount: _results.length,
                            itemBuilder: (context, i) => GestureDetector(
                              onTap: () => Navigator.pop(context, _results[i]['url'] as String),
                              child: ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.network(_results[i]['preview'], fit: BoxFit.cover)),
                            ),
                          ),
          ),
          const Padding(padding: EdgeInsets.only(bottom: 6), child: Text('Powered by GIPHY', style: TextStyle(fontSize: 10))),
        ]),
      ),
    );
  }
}
