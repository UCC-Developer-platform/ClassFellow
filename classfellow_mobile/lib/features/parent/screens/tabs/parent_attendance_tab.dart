import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_endpoints.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../models/parent_models.dart';

class ParentAttendanceTab extends StatefulWidget {
  final int enrollmentId;

  const ParentAttendanceTab({super.key, required this.enrollmentId});

  @override
  State<ParentAttendanceTab> createState() => _ParentAttendanceTabState();
}

class _ParentAttendanceTabState extends State<ParentAttendanceTab> {
  DateTime _currentMonth = DateTime.now();
  bool _isLoading = true;
  String? _errorMessage;
  AttendanceSummaryResponse? _attendanceData;

  @override
  void initState() {
    super.initState();
    _fetchAttendance();
  }

  @override
  void didUpdateWidget(covariant ParentAttendanceTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.enrollmentId != widget.enrollmentId) {
      _fetchAttendance();
    }
  }

  String get _monthYearString => DateFormat('yyyy-MM').format(_currentMonth);
  String get _monthYearDisplay => DateFormat('MMMM yyyy').format(_currentMonth);

  Future<void> _fetchAttendance() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final apiClient = context.read<ApiClient>();
    try {
      final response = await apiClient.get(
        ApiEndpoints.parentAttendance,
        queryParams: {
          'enrollment_id': widget.enrollmentId.toString(),
          'month_year': _monthYearString,
        },
      );

      if (response is Map<String, dynamic>) {
        setState(() {
          _attendanceData = AttendanceSummaryResponse.fromJson(response);
          _isLoading = false;
        });
      } else {
        setState(() {
          _errorMessage = 'Invalid attendance response format.';
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

  void _previousMonth() {
    setState(() {
      _currentMonth = DateTime(_currentMonth.year, _currentMonth.month - 1);
    });
    _fetchAttendance();
  }

  void _nextMonth() {
    setState(() {
      _currentMonth = DateTime(_currentMonth.year, _currentMonth.month + 1);
    });
    _fetchAttendance();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Month Selector Bar
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          decoration: const BoxDecoration(
            color: AppTheme.cardBackground,
            border: Border(bottom: BorderSide(color: AppTheme.cardBorder)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              IconButton(
                icon: const Icon(Icons.chevron_left_rounded, color: AppTheme.textPrimary),
                onPressed: _previousMonth,
              ),
              Text(
                _monthYearDisplay,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
              IconButton(
                icon: const Icon(Icons.chevron_right_rounded, color: AppTheme.textPrimary),
                onPressed: _nextMonth,
              ),
            ],
          ),
        ),

        // Main Attendance Content
        Expanded(child: _buildBody()),
      ],
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.emerald500));
    }

    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.rose500),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _fetchAttendance,
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.emerald500),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_attendanceData == null) {
      return const Center(child: Text('No attendance data available.', style: TextStyle(color: AppTheme.textMuted)));
    }

    final data = _attendanceData!;
    Color pctColor = AppTheme.emerald500;
    if (data.attendancePercentage < 75.0) {
      pctColor = AppTheme.rose500;
    } else if (data.attendancePercentage < 85.0) {
      pctColor = AppTheme.amber500;
    }

    return RefreshIndicator(
      onRefresh: _fetchAttendance,
      color: AppTheme.emerald500,
      backgroundColor: AppTheme.cardBackground,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Header Summary Card
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.cardBackground,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.cardBorder),
            ),
            child: Row(
              children: [
                // Circular percentage badge
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: pctColor.withOpacity(0.12),
                    border: Border.all(color: pctColor, width: 3),
                  ),
                  alignment: Alignment.center,
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '${data.attendancePercentage.toStringAsFixed(1)}%',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: pctColor,
                        ),
                      ),
                      const Text(
                        'Rate',
                        style: TextStyle(fontSize: 10, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 20),

                // Counts breakdown
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          _buildCountChip('Present', data.presentDays, AppTheme.emerald500),
                          _buildCountChip('Absent', data.absentDays, AppTheme.rose500),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          _buildCountChip('Leave', data.leaveDays, AppTheme.amber500),
                          _buildCountChip('Late', data.lateDays, Colors.purpleAccent),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Daily Records Title
          Text(
            'Daily Attendance Records (${data.records.length} days)',
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 12),

          if (data.records.isEmpty)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 32),
              alignment: Alignment.center,
              child: const Text('No attendance recorded for this month.', style: TextStyle(color: AppTheme.textMuted)),
            )
          else
            ...data.records.map((rec) => _buildDayTile(rec)),
        ],
      ),
    );
  }

  Widget _buildCountChip(String label, int count, Color color) {
    return Row(
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(shape: BoxShape.circle, color: color),
        ),
        const SizedBox(width: 6),
        Text(
          '$label: ',
          style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
        ),
        Text(
          count.toString(),
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
        ),
      ],
    );
  }

  Widget _buildDayTile(AttendanceRecordItem record) {
    Color statusColor = AppTheme.emerald500;
    IconData statusIcon = Icons.check_circle_outline_rounded;

    if (record.status == 'ABSENT') {
      statusColor = AppTheme.rose500;
      statusIcon = Icons.cancel_outlined;
    } else if (record.status == 'LEAVE') {
      statusColor = AppTheme.amber500;
      statusIcon = Icons.access_time_rounded;
    } else if (record.status == 'LATE') {
      statusColor = Colors.purpleAccent;
      statusIcon = Icons.hourglass_bottom_rounded;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppTheme.cardBackground,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Row(
        children: [
          Icon(statusIcon, color: statusColor, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  record.date,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                    color: AppTheme.textPrimary,
                  ),
                ),
                if (record.remarks != null && record.remarks!.isNotEmpty)
                  Text(
                    record.remarks!,
                    style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                  ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.15),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              record.status,
              style: TextStyle(
                color: statusColor,
                fontSize: 11,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
