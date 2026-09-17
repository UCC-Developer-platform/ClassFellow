import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/theme/app_theme.dart';
import '../../../models/teacher_models.dart';

class AttendanceRosterScreen extends StatefulWidget {
  final int classGroupId;
  final String className;
  final String section;
  final String? subjectName;

  const AttendanceRosterScreen({
    super.key,
    required this.classGroupId,
    required this.className,
    required this.section,
    this.subjectName,
  });

  @override
  State<AttendanceRosterScreen> createState() => _AttendanceRosterScreenState();
}

class _AttendanceRosterScreenState extends State<AttendanceRosterScreen> {
  DateTime _selectedDate = DateTime.now();
  bool _isLoading = true;
  bool _isSaving = false;
  String? _errorMessage;
  List<RosterStudent> _roster = [];
  final Map<int, String> _attendanceStatus = {}; // enrollmentId -> status string

  @override
  void initState() {
    super.initState();
    _fetchRoster();
  }

  String get _formattedDate => DateFormat('yyyy-MM-dd').format(_selectedDate);

  Future<void> _fetchRoster() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final apiClient = context.read<ApiClient>();
    try {
      final response = await apiClient.get(
        ApiEndpoints.teacherRoster,
        queryParams: {
          'class_group_id': widget.classGroupId.toString(),
          'date': _formattedDate,
        },
      );

      if (response is Map<String, dynamic>) {
        final rosterResponse = RosterResponse.fromJson(response);
        setState(() {
          _roster = rosterResponse.roster;
          _attendanceStatus.clear();
          for (final student in _roster) {
            _attendanceStatus[student.enrollmentId] =
                student.attendanceStatus ?? 'PRESENT';
          }
          _isLoading = false;
        });
      } else {
        setState(() {
          _errorMessage = 'Invalid response received from server.';
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

  Future<void> _selectDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(2020),
      lastDate: DateTime.now().add(const Duration(days: 7)),
      builder: (context, child) {
        return Theme(
          data: ThemeData.dark().copyWith(
            colorScheme: const ColorScheme.dark(
              primary: AppTheme.emerald500,
              onPrimary: Colors.white,
              surface: AppTheme.cardBackground,
              onSurface: AppTheme.textPrimary,
            ),
            dialogBackgroundColor: AppTheme.cardBackground,
          ),
          child: child!,
        );
      },
    );

    if (picked != null && picked != _selectedDate) {
      setState(() {
        _selectedDate = picked;
      });
      _fetchRoster();
    }
  }

  void _markAllPresent() {
    setState(() {
      for (final student in _roster) {
        _attendanceStatus[student.enrollmentId] = 'PRESENT';
      }
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Marked all students as Present'),
        backgroundColor: AppTheme.emerald600,
        duration: Duration(seconds: 1),
      ),
    );
  }

  Future<void> _saveAttendance() async {
    if (_roster.isEmpty) return;

    setState(() {
      _isSaving = true;
    });

    final apiClient = context.read<ApiClient>();
    final entries = _roster.map((student) {
      return {
        'enrollment_id': student.enrollmentId,
        'status': _attendanceStatus[student.enrollmentId] ?? 'PRESENT',
        'reason_note': '',
      };
    }).toList();

    try {
      final payload = {
        'class_group_id': widget.classGroupId,
        'attendance_date': _formattedDate,
        'attendance_entries': entries,
      };

      final response = await apiClient.post(
        ApiEndpoints.teacherAttendanceSave,
        body: payload,
      );

      if (!mounted) return;

      int updatedCount = entries.length;
      if (response is Map && response.containsKey('saved_count')) {
        updatedCount = response['saved_count'] as int;
      } else if (response is Map && response.containsKey('records_processed')) {
        updatedCount = response['records_processed'] as int;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Successfully saved attendance for $updatedCount students.',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          backgroundColor: AppTheme.emerald600,
          behavior: SnackBarBehavior.floating,
        ),
      );

      Navigator.of(context).pop();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to save attendance: $e'),
          backgroundColor: AppTheme.rose500,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSaving = false;
        });
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
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${widget.className} (${widget.section})',
              style: const TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            Text(
              widget.subjectName ?? 'Daily Attendance Roster',
              style: const TextStyle(
                fontSize: 12,
                color: AppTheme.emerald500,
              ),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          // Control Bar: Date picker & Mark All Present button
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: const BoxDecoration(
              color: AppTheme.cardBackground,
              border: Border(
                bottom: BorderSide(color: AppTheme.cardBorder, width: 1),
              ),
            ),
            child: Row(
              children: [
                // Date Picker Chip
                InkWell(
                  onTap: _selectDate,
                  borderRadius: BorderRadius.circular(10),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppTheme.slate900,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppTheme.cardBorder),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.calendar_today_rounded,
                          size: 16,
                          color: AppTheme.emerald500,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _formattedDate,
                          style: const TextStyle(
                            color: AppTheme.textPrimary,
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                          ),
                        ),
                        const SizedBox(width: 4),
                        const Icon(
                          Icons.arrow_drop_down_rounded,
                          color: AppTheme.textMuted,
                        ),
                      ],
                    ),
                  ),
                ),
                const Spacer(),

                // Mark All Present Action
                OutlinedButton.icon(
                  onPressed: _roster.isNotEmpty ? _markAllPresent : null,
                  icon: const Icon(Icons.done_all_rounded, size: 16, color: AppTheme.emerald500),
                  label: const Text(
                    'All Present',
                    style: TextStyle(color: AppTheme.emerald500, fontSize: 13),
                  ),
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: AppTheme.emerald500),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Main Roster List
          Expanded(child: _buildRosterBody()),

          // Bottom Bar: Save Button
          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              color: AppTheme.cardBackground,
              border: Border(
                top: BorderSide(color: AppTheme.cardBorder, width: 1),
              ),
            ),
            child: SafeArea(
              child: ElevatedButton(
                onPressed: (_isSaving || _roster.isEmpty) ? null : _saveAttendance,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.emerald500,
                  foregroundColor: Colors.white,
                  minimumSize: const Size.fromHeight(48),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: _isSaving
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.check_circle_outline_rounded, size: 20),
                          const SizedBox(width: 8),
                          Text(
                            'Save Attendance (${_roster.length} Students)',
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRosterBody() {
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
              const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.rose500),
              const SizedBox(height: 12),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _fetchRoster,
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.emerald500),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_roster.isEmpty) {
      return const Center(
        child: Text(
          'No enrolled students found for this class.',
          style: TextStyle(color: AppTheme.textMuted),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      itemCount: _roster.length,
      itemBuilder: (context, index) {
        final student = _roster[index];
        final currentStatus = _attendanceStatus[student.enrollmentId] ?? 'PRESENT';

        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppTheme.cardBackground,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.cardBorder),
          ),
          child: Row(
            children: [
              // Roll Number Badge
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: AppTheme.slate700,
                  borderRadius: BorderRadius.circular(8),
                ),
                alignment: Alignment.center,
                child: Text(
                  student.rollNumber != null && student.rollNumber!.isNotEmpty
                      ? student.rollNumber!
                      : '#${index + 1}',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                    fontSize: 13,
                  ),
                ),
              ),
              const SizedBox(width: 12),

              // Student Details
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      student.fullName,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Adm: ${student.admissionNumber}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textMuted,
                      ),
                    ),
                  ],
                ),
              ),

              // Status Toggles (P, A, L, T)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _buildStatusButton(
                    label: 'P',
                    status: 'PRESENT',
                    currentStatus: currentStatus,
                    activeColor: AppTheme.emerald500,
                    enrollmentId: student.enrollmentId,
                  ),
                  const SizedBox(width: 4),
                  _buildStatusButton(
                    label: 'A',
                    status: 'ABSENT',
                    currentStatus: currentStatus,
                    activeColor: AppTheme.rose500,
                    enrollmentId: student.enrollmentId,
                  ),
                  const SizedBox(width: 4),
                  _buildStatusButton(
                    label: 'L',
                    status: 'LEAVE',
                    currentStatus: currentStatus,
                    activeColor: AppTheme.amber500,
                    enrollmentId: student.enrollmentId,
                  ),
                  const SizedBox(width: 4),
                  _buildStatusButton(
                    label: 'T',
                    status: 'LATE',
                    currentStatus: currentStatus,
                    activeColor: Colors.purpleAccent,
                    enrollmentId: student.enrollmentId,
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildStatusButton({
    required String label,
    required String status,
    required String currentStatus,
    required Color activeColor,
    required int enrollmentId,
  }) {
    final isSelected = currentStatus.toUpperCase() == status.toUpperCase();

    return InkWell(
      onTap: () {
        setState(() {
          _attendanceStatus[enrollmentId] = status;
        });
      },
      borderRadius: BorderRadius.circular(8),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: 32,
        height: 32,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: isSelected ? activeColor : AppTheme.slate800,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? activeColor : AppTheme.cardBorder,
            width: 1.5,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : AppTheme.textMuted,
            fontWeight: FontWeight.bold,
            fontSize: 13,
          ),
        ),
      ),
    );
  }
}
