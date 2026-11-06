import 'package:flutter/material.dart';

import '../api.dart';
import '../util.dart';

/// An image from the backend, fetched with the signed-in session (photos aren't public).
class ApiImage extends StatelessWidget {
  const ApiImage(this.path, {super.key, this.fit = BoxFit.cover, this.width, this.height});
  final String path;
  final BoxFit fit;
  final double? width, height;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder(
      future: api.bytes(path),
      builder: (context, snap) {
        if (snap.hasData) return Image.memory(snap.data!, fit: fit, width: width, height: height, gaplessPlayback: true);
        return Container(
          width: width,
          height: height ?? 160,
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: snap.hasError ? const Icon(Icons.broken_image_outlined) : const Center(child: CircularProgressIndicator(strokeWidth: 2)),
        );
      },
    );
  }
}

class Avatar extends StatelessWidget {
  const Avatar(this.person, {super.key, this.radius = 20, this.online = false});
  final Json? person;
  final double radius;
  final bool online;

  @override
  Widget build(BuildContext context) {
    final avatar = person?['avatar'] as String?;
    Widget inner = CircleAvatar(
      radius: radius,
      child: Text(initials(person), style: TextStyle(fontSize: radius * 0.7)),
    );
    if (avatar != null && avatar.isNotEmpty) {
      final path = avatar.startsWith('http') ? Uri.parse(avatar).path : avatar;
      inner = ClipOval(child: SizedBox(width: radius * 2, height: radius * 2, child: ApiImage(path, width: radius * 2, height: radius * 2)));
    }
    if (!online) return inner;
    return Stack(clipBehavior: Clip.none, children: [
      inner,
      Positioned(
        right: -1,
        bottom: -1,
        child: Container(
          width: radius * 0.55,
          height: radius * 0.55,
          decoration: BoxDecoration(color: Colors.green, shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 2)),
        ),
      ),
    ]);
  }
}
