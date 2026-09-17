import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'core/network/api_client.dart';
import 'core/storage/secure_storage_service.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/screens/login_screen.dart';
import 'features/parent/screens/parent_home_screen.dart';
import 'features/teacher/screens/teacher_home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: AppTheme.slate900,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  final storageService = SecureStorageService();
  final apiClient = ApiClient();

  runApp(
    MultiProvider(
      providers: [
        Provider<SecureStorageService>.value(value: storageService),
        Provider<ApiClient>.value(value: apiClient),
        ChangeNotifierProvider<AuthController>(
          create: (_) => AuthController(
            apiClient: apiClient,
            storageService: storageService,
          ),
        ),
      ],
      child: const ClassFellowMobileApp(),
    ),
  );
}

class ClassFellowMobileApp extends StatelessWidget {
  const ClassFellowMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ClassFellow Mobile',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const AuthGate(),
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  late Future<bool> _autoLoginFuture;

  @override
  void initState() {
    super.initState();
    _autoLoginFuture = context.read<AuthController>().tryAutoLogin();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _autoLoginFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            backgroundColor: AppTheme.slate900,
            body: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.school_rounded,
                    size: 64,
                    color: AppTheme.emerald500,
                  ),
                  SizedBox(height: 24),
                  CircularProgressIndicator(color: AppTheme.emerald500),
                ],
              ),
            ),
          );
        }

        final isLoggedIn = snapshot.data ?? false;
        if (isLoggedIn) {
          final session = context.read<AuthController>().session;
          if (session != null && session.isParent) {
            return const ParentHomeScreen();
          }
          return const TeacherHomeScreen();
        }

        return const LoginScreen();
      },
    );
  }
}
