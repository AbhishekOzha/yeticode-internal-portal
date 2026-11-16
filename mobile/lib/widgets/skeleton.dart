import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

/// Grey shimmering placeholders shown while a list loads, instead of a bare spinner.
class SkeletonList extends StatelessWidget {
  const SkeletonList({super.key, this.count = 6, this.avatar = true});
  final int count;
  final bool avatar;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    Widget bar(double w, double h) => Container(width: w, height: h, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8)));
    return Shimmer.fromColors(
      baseColor: dark ? const Color(0xFF26273D) : const Color(0xFFE6E8F0),
      highlightColor: dark ? const Color(0xFF34365A) : const Color(0xFFF7F8FC),
      child: ListView(
        physics: const NeverScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          for (var i = 0; i < count; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 18),
              child: Row(children: [
                if (avatar) Container(width: 48, height: 48, decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle)),
                if (avatar) const SizedBox(width: 14),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [bar(160, 14), const SizedBox(height: 8), bar(double.infinity, 12)])),
              ]),
            ),
        ],
      ),
    );
  }
}
