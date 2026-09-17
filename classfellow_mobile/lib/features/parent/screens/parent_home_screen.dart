import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/theme/app_theme.dart';
import '../../../models/parent_models.dart';
import '../../auth/auth_controller.dart';
import '../../auth/screens/login_screen.dart';
import 'tabs/parent_fee_tab.dart';
import 'tabs/parent_attendance_tab.dart';
import 'tabs/parent_report_card_tab.dart';

class ParentHomeScreen extends StatefulWidget {
  const ParentHomeScreen({super.key});

  @override
  State<ParentHomeScreen> createState() => _ParentHomeScreenState();
}

class _ParentHomeScreenState extends State<ParentHomeScreen> {
  int _currentTabIndex = 0;
  bool _isLoading = true;
  String? _errorMessage;
  List<ChildProfile> _children = [];
  int? _selectedEnrollmentId;

  @override
  void initState() {
    super.initState();
    _fetchChildren();
  }

  Future<void> _fetchChildren() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final apiClient = context.read<ApiClient>();
    try {
      final response = await apiClient.get(ApiEndpoints.parentChildren);
      if (response is List) {
        final childrenList = response
            .map((item) => ChildProfile.fromJson(item as Map<String, dynamic>))
            .toList();

        setState(() {
          _children = childrenList;
          if (_children.isNotEmpty) {
            _selectedEnrollmentId = _children.first.enrollmentId;
          }
          _isLoading = false;
        });
      } else {
        setState(() {
          _errorMessage = 'Invalid children profile response.';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _confirmLogout() async {
    final shouldLogout = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.cardBackground,
        title: const Text('Sign Out', style: TextStyle(color: AppTheme.textPrimary)),
        content: const Text(
          'Are you sure you want to sign out of ClassFellow?',
          style: TextStyle(color: AppTheme.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel', style: TextStyle(color: AppTheme.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.rose500),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Sign Out', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (shouldLogout == true && mounted) {
      await context.read<AuthController>().logout();
      if (mounted) {
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => const LoginScreen()),
          (route) => false,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.slate900,
      appBar: AppBar(
        backgroundColor: AppTheme.slate800,
        elevation: 0,
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Parent Portal',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            Text(
              'Student Progress & Institutional Records',
              style: TextStyle(
                fontSize: 12,
                color: AppTheme.emerald500,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: AppTheme.textSecondary),
            tooltip: 'Refresh',
            onPressed: _fetchChildren,
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded, color: AppTheme.rose500),
            tooltip: 'Sign Out',
            onPressed: _confirmLogout,
          ),
        ],
      ),
      body: _buildBody(),
      bottomNavigationBar: _children.isNotEmpty && _selectedEnrollmentId != null
          ? Container(
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: AppTheme.cardBorder, width: 1)),
              ),
              child: BottomNavigationBar(
                currentIndex: _currentTabIndex,
                backgroundColor: AppTheme.slate800,
                selectedItemColor: AppTheme.emerald500,
                unselectedItemColor: AppTheme.textMuted,
                selectedFontSize: 12,
                unselectedFontSize: 12,
                type: BottomNavigationBarType.fixed,
                onTap: (index) {
                  setState(() {
                    _currentTabIndex = index;
                  });
                },
                items: const [
                  BottomNavigationBarItem(
                    icon: Icon(Icons.account_balance_wallet_outlined),
                    activeIcon: Icon(Icons.account_balance_wallet_rounded),
                    label: 'Fees',
                  ),
                  BottomNavigationBarItem(
                    icon: Icon(Icons.calendar_today_outlined),
                    activeIcon: Icon(Icons.calendar_today_rounded),
                    label: 'Attendance',
                  ),
                  BottomNavigationBarItem(
                    icon: Icon(Icons.school_outlined),
                    activeIcon: Icon(Icons.school_rounded),
                    label: 'Report Card',
                  ),
                ],
              ),
            )
          : null,
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.emerald500),
      );
    }

    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_rounded, size: 48, color: AppTheme.rose500),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _fetchChildren,
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.emerald500),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_children.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: const BoxDecoration(
                  color: AppTheme.slate800,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.people_outline_rounded, size: 48, color: AppTheme.textMuted),
              ),
              const SizedBox(height: 16),
              const Text(
                'No Registered Children Found',
                style: TextStyle(color: AppTheme.textPrimary, fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              const Text(
                'No student records matched your registered emergency contact phone or CNIC. Please contact the campus administration office.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppTheme.textMuted, fontSize: 13),
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      children: [
        // Multi-Child Switcher Chip Bar
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: const BoxDecoration(
            color: AppTheme.cardBackground,
            border: Border(bottom: BorderSide(color: AppTheme.cardBorder)),
          ),
          child: SizedBox(
            height: 40,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: _children.length,
              itemBuilder: (context, index) {
                final child = _children[index];
                final isSelected = child.enrollmentId == _selectedEnrollmentId;

                return Padding(
                  padding: const EdgeInsets.only(right: 8.0),
                  child: FilterChip(
                    label: Text('${child.fullName} (${child.className}-${child.section})'),
                    selected: isSelected,
                    onSelected: (selected) {
                      if (selected) {
                        setState(() {
                          _selectedEnrollmentId = child.enrollmentId;
                        });
                      }
                    },
                    backgroundColor: AppTheme.slate900,
                    selectedColor: AppTheme.emerald500.withOpacity(0.2),
                    checkmarkColor: AppTheme.emerald500,
                    side: BorderSide(
                      color: isSelected ? AppTheme.emerald500 : AppTheme.cardBorder,
                      width: 1.5,
                    ),
                    labelStyle: TextStyle(
                      color: isSelected ? AppTheme.emerald500 : AppTheme.textSecondary,
                      fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      fontSize: 13,
                    ),
                  ),
                );
              },
            ),
          ),
        ),

        // Active Child Tab View
        Expanded(
          child: IndexedStack(
            index: _currentTabIndex,
            children: [
              ParentFeeTab(enrollmentId: _selectedEnrollmentId!),
              ParentAttendanceTab(enrollmentId: _selectedEnrollmentId!),
              ParentReportCardTab(enrollmentId: _selectedEnrollmentId!),
            ],
          ),
        ),
      ],
    );
  }
}
