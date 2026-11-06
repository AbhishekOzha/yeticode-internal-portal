import 'dart:io';
import 'dart:typed_data';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

typedef Json = Map<String, dynamic>;

class ApiError implements Exception {
  ApiError(this.status, this.message);
  final int? status;
  final String message;
  @override
  String toString() => message;
}

String _describe(dynamic data) {
  if (data is! Map) return '';
  if (data['detail'] != null) return data['detail'].toString();
  return data.entries.map((e) {
    final text = e.value is List ? (e.value as List).join(' ') : e.value.toString();
    return e.key == 'non_field_errors' ? text : '${e.key.toString().replaceAll('_', ' ')}: $text';
  }).join(' ');
}

/// Talks to the Django backend with the same session cookie + CSRF token the website uses.
class Api {
  Api._();
  static final Api i = Api._();

  late Dio _dio;
  late PersistCookieJar _jar;
  String baseUrl = Platform.isAndroid ? 'http://10.0.2.2:9000' : 'http://localhost:9000';
  final _imageCache = <String, Uint8List>{};

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    baseUrl = prefs.getString('server') ?? baseUrl;
    final dir = await getApplicationDocumentsDirectory();
    _jar = PersistCookieJar(storage: FileStorage('${dir.path}/.cookies/'));
    _build();
  }

  void _build() {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
      validateStatus: (_) => true,
    ));
    _dio.interceptors.add(CookieManager(_jar));
  }

  Future<void> setServer(String url) async {
    baseUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    (await SharedPreferences.getInstance()).setString('server', baseUrl);
    _imageCache.clear();
    _build();
  }

  Future<String> _csrf() async {
    final cookies = await _jar.loadForRequest(Uri.parse(baseUrl));
    for (final c in cookies) {
      if (c.name == 'csrftoken') return c.value;
    }
    await _dio.get('/api/auth/csrf/');
    for (final c in await _jar.loadForRequest(Uri.parse(baseUrl))) {
      if (c.name == 'csrftoken') return c.value;
    }
    return '';
  }

  Future<dynamic> _send(String method, String path, {dynamic body}) async {
    final options = Options(method: method, headers: {'Accept': 'application/json'});
    if (method != 'GET') options.headers!['X-CSRFToken'] = await _csrf();
    try {
      final response = await _dio.request('/api$path', data: body, options: options);
      final status = response.statusCode ?? 0;
      if (status == 204) return null;
      if (status >= 400) {
        throw ApiError(status, _describe(response.data).isEmpty ? 'Request failed ($status)' : _describe(response.data));
      }
      return response.data;
    } on DioException catch (e) {
      throw ApiError(null, 'Cannot reach the server at $baseUrl. ${e.message ?? ''}'.trim());
    }
  }

  Future<Json> get(String path) async => Map<String, dynamic>.from(await _send('GET', path));
  Future<Json?> post(String path, [dynamic body]) async {
    final r = await _send('POST', path, body: body);
    return r == null ? null : Map<String, dynamic>.from(r);
  }

  Future<Json?> patch(String path, dynamic body) async {
    final r = await _send('PATCH', path, body: body);
    return r == null ? null : Map<String, dynamic>.from(r);
  }

  Future<Json?> delete(String path) async {
    final r = await _send('DELETE', path);
    return r is Map ? Map<String, dynamic>.from(r) : null;
  }

  /// Fetches a protected file (photo, voice message...) with the session cookie.
  Future<Uint8List> bytes(String path) async {
    if (_imageCache.containsKey(path)) return _imageCache[path]!;
    final response = await _dio.get<List<int>>(path, options: Options(responseType: ResponseType.bytes));
    if ((response.statusCode ?? 0) >= 400) throw ApiError(response.statusCode, 'Could not load the file.');
    final data = Uint8List.fromList(response.data!);
    if (data.length < 3 * 1024 * 1024) _imageCache[path] = data;
    return data;
  }

  Future<File> download(String path, String name) async {
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/$name');
    await file.writeAsBytes(await bytes(path));
    return file;
  }

  // Auth --------------------------------------------------------------
  Future<Json?> session() async => (await get('/auth/session/'))['user'] as Json?;
  Future<Json> login(String username, String password) async =>
      (await post('/auth/login/', {'username': username, 'password': password}))!;
  Future<void> logout() async {
    await post('/auth/logout/');
    _imageCache.clear();
  }

  Future<Json> branding() => get('/branding/');
}

final api = Api.i;
