import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/theme/app_theme.dart';
import '../../../models/teacher_models.dart';

class MarksEntryScreen extends StatefulWidget {
  final int classGroupId;
  final String className;
  final String section;
  final int? subjectId;
  final String subjectName;
  final int? examSubjectId;

  const MarksEntryScreen({
    super.key,
    required this.classGroupId,
    required this.className,
    required this.section,
    this.subjectId,
    required this.subjectName,
    this.examSubjectId,
  });

  @override
  State<MarksEntryScreen> createState() => _MarksEntryScreenState();
}

class _MarksEntryScreenState extends State<MarksEntryScreen> {
  final double _maxMarks = 100.0;
  bool _isLoading = true;
  bool _isSaving = false;
  String? _errorMessage;

  List<RosterStudent> _students = [];
  final Map<int, TextEditingController> _marksControllers = {};
  final Map<int, bool> _absentStatus = {};
  final Map<int, String?> _fieldErrors = {};

  @override
  void initState() {
    super.initState();
    _loadStudents();
  }

  @override
  void dispose() {
    for (final controller in _marksControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _loadStudents() async {
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
        },
      );

      if (response is Map<String, dynamic>) {
        final rosterResponse = RosterResponse.fromJson(response);
        setState(() {
          _students = rosterResponse.roster;
          _marksControllers.clear();
          _absentStatus.clear();
          _fieldErrors.clear();

          for (final student in _students) {
            _marksControllers[student.enrollmentId] = TextEditingController();
            _absentStatus[student.enrollmentId] = false;
          }
          _isLoading = false;
        });
      } else {
        setState(() {
          _errorMessage = 'Invalid response from roster service.';
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

  bool _validateMarks(int enrollmentId, String text) {
    if (_absentStatus[enrollmentId] == true) {
      _fieldErrors[enrollmentId] = null;
      return true;
    }

    if (text.trim().isEmpty) {
      _fieldErrors[enrollmentId] = null; // optional or unentered
      return true;
    }

    final val = double.tryParse(text.trim());
    if (val == null) {
      _fieldErrors[enrollmentId] = 'Invalid number';
      return false;
    }

    if (val < 0.0 || val > _maxMarks) {
      _fieldErrors[enrollmentId] = 'Must be between 0 and ${_maxMarks.toInt()}';
      return false;
    }

    _fieldErrors[enrollmentId] = null;
    return true;
  }

  Future<void> _saveMarks() async {
    // Validate all inputs
    bool hasValidationError = false;
    for (final student in _students) {
      final id = student.enrollmentId;
      final text = _marksControllers[id]?.text ?? '';
      if (!_validateMarks(id, text)) {
        hasValidationError = true;
      }
    }

    if (hasValidationError) {
      setState(() {});
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please correct out-of-bounds marks before saving.'),
          backgroundColor: AppTheme.rose500,
        ),
      );
      return;
    }

    setState(() {
      _isSaving = true;
    });

    final apiClient = context.read<ApiClient>();
    final targetExamSubjectId = widget.examSubjectId ?? widget.subjectId ?? 1;

    final marksPayload = <Map<String, dynamic>>[];
    for (final student in _students) {
      final id = student.enrollmentId;
      final isAbsent = _absentStatus[id] ?? false;
      final text = _marksControllers[id]?.text.trim() ?? '';

      if (isAbsent || text.isNotEmpty) {
        marksPayload.add({
          'exam_subject_id': targetExamSubjectId,
          'enrollment_id': id,
          'marks_obtained': isAbsent ? '0.00' : (text.isEmpty ? '0.00' : text),
          'is_absent': isAbsent,
          'remarks': isAbsent ? 'Marked absent by faculty' : '',
        });
      }
    }

    if (marksPayload.isEmpty) {
      setState(() {
        _isSaving = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No marks entered to save.'),
          backgroundColor: AppTheme.amber500,
        ),
      );
      return;
    }

    try {
      final response = await apiClient.post(
        ApiEndpoints.teacherMarksSave,
        body: {'marks': marksPayload},
      );

      if (!mounted) return;

      int savedCount = marksPayload.length;
      if (response is Map && response.containsKey('recorded_count')) {
        savedCount = response['recorded_count'] as int;
      } else if (response is Map && response.containsKey('records_saved')) {
        savedCount = response['records_saved'] as int;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Successfully saved marks for $savedCount students.',
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
          content: Text('Failed to save marks: $e'),
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
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            Text(
              '${widget.subjectName} • Max Marks: ${_maxMarks.toInt()}',
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
          // Banner info
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            color: AppTheme.cardBackground,
            child: Row(
              children: [
                const Icon(Icons.info_outline_rounded, size: 18, color: AppTheme.textMuted),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Bounds: 0.00 to ${_maxMarks.toInt()}.00. Check "Absent" if student did not sit for exam.',
                    style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
                  ),
                ),
              ],
            ),
          ),

          Expanded(child: _buildBody()),

          // Bottom Bar
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
                onPressed: (_isSaving || _students.isEmpty) ? null : _saveMarks,
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
                    : const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.save_rounded, size: 20),
                          SizedBox(width: 8),
                          Text(
                            'Save Examination Marks',
                            style: TextStyle(
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

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.emerald500),
      );
    }

    if (_errorMessage != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.rose500),
            const SizedBox(height: 12),
            Text(_errorMessage!, style: const TextStyle(color: AppTheme.textSecondary)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadStudents,
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.emerald500),
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      itemCount: _students.length,
      itemBuilder: (context, index) {
        final student = _students[index];
        final id = student.enrollmentId;
        final isAbsent = _absentStatus[id] ?? false;
        final fieldError = _fieldErrors[id];

        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppTheme.cardBackground,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: fieldError != null ? AppTheme.rose500 : AppTheme.cardBorder,
              width: fieldError != null ? 1.5 : 1.0,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  // Roll badge
                  Container(
                    width: 34,
                    height: 34,
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
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),

                  // Student name
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          student.fullName,
                          style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        Text(
                          'Adm: ${student.admissionNumber}',
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppTheme.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Absent checkbox
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Checkbox(
                        value: isAbsent,
                        activeColor: AppTheme.rose500,
                        checkColor: Colors.white,
                        onChanged: (val) {
                          setState(() {
                            _absentStatus[id] = val ?? false;
                            if (val == true) {
                              _marksControllers[id]?.text = '';
                              _fieldErrors[id] = null;
                            }
                          });
                        },
                      ),
                      const Text(
                        'Absent',
                        style: TextStyle(
                          color: AppTheme.rose500,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(width: 8),

                  // Marks Input
                  SizedBox(
                    width: 80,
                    child: TextField(
                      controller: _marksControllers[id],
                      enabled: !isAbsent,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: [
                        FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}')),
                      ],
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: isAbsent ? AppTheme.textMuted : AppTheme.textPrimary,
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                      ),
                      onChanged: (val) {
                        setState(() {
                          _validateMarks(id, val);
                        });
                      },
                      decoration: InputDecoration(
                        hintText: isAbsent ? 'ABS' : '0.0',
                        contentPadding: const EdgeInsets.symmetric(
                          vertical: 10,
                          horizontal: 8,
                        ),
                        fillColor: isAbsent ? AppTheme.slate800 : AppTheme.slate900,
                        filled: true,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: BorderSide(
                            color: fieldError != null ? AppTheme.rose500 : AppTheme.cardBorder,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              if (fieldError != null)
                Padding(
                  padding: const EdgeInsets.only(top: 6, left: 44),
                  child: Text(
                    fieldError,
                    style: const TextStyle(
                      color: AppTheme.rose500,
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}
