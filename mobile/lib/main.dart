import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'api.dart';
import 'call.dart';
import 'screens/home.dart';
import 'screens/login.dart';
import 'state.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await api.init();
  final state = AppState();
  final calls = CallController(state);
  state.start();
  runApp(MultiProvider(
    providers: [
      ChangeNotifierProvider.value(value: state),
      ChangeNotifierProvider.value(value: calls),
    ],
    child: const YeticodeApp(),
  ));
}

class YeticodeApp extends StatelessWidget {
  const YeticodeApp({super.key});

  @override
  Widget build(BuildContext context) {
    ThemeData theme(Brightness b) => ThemeData(
          colorSchemeSeed: const Color(0xFF2F54EB),
          brightness: b,
          useMaterial3: true,
        );
    return MaterialApp(
      title: 'Yeticode',
      debugShowCheckedModeBanner: false,
      theme: theme(Brightness.light),
      darkTheme: theme(Brightness.dark),
      builder: (context, child) => Stack(children: [child!, const CallOverlay()]),
      home: Consumer<AppState>(
        builder: (context, state, _) {
          if (!state.ready) return const Scaffold(body: Center(child: CircularProgressIndicator()));
          return state.signedIn ? const Home() : const LoginScreen();
        },
      ),
    );
  }
}
