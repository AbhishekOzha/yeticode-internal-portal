import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state.dart';
import 'chats.dart';
import 'feed.dart';
import 'more.dart';
import 'notifications.dart';

class Home extends StatefulWidget {
  const Home({super.key});
  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final team = state.inTeam;
    final pages = <Widget>[
      if (team) const FeedScreen(),
      if (team) const ChatsScreen(),
      const MoreScreen(),
    ];
    final index = _tab.clamp(0, pages.length - 1);
    return Scaffold(
      appBar: AppBar(
        title: Text(state.branding['name']?.toString() ?? 'Yeticode'),
        actions: [
          IconButton(
            icon: Badge(isLabelVisible: state.notificationsUnread > 0, label: Text('${state.notificationsUnread}'), child: const Icon(Icons.notifications_outlined)),
            onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen())),
          ),
        ],
      ),
      body: IndexedStack(index: index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: [
          if (team) const NavigationDestination(icon: Icon(Icons.dynamic_feed_outlined), selectedIcon: Icon(Icons.dynamic_feed), label: 'Feed'),
          if (team)
            NavigationDestination(
              icon: Badge(isLabelVisible: state.totalUnread > 0, label: Text('${state.totalUnread}'), child: const Icon(Icons.chat_bubble_outline)),
              selectedIcon: const Icon(Icons.chat_bubble),
              label: 'Chats',
            ),
          const NavigationDestination(icon: Icon(Icons.menu), label: 'More'),
        ],
      ),
    );
  }
}
