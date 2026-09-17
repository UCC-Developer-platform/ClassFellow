import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_endpoints.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../models/parent_models.dart';

class ParentReportCardTab extends StatefulWidget {
  final int enrollmentId;

  const ParentReportCardTab({super.key, required this.enrollmentId});

  @override
  State<ParentReportCardTab> createState() => _ParentReportCardTabState();
}

class _ParentReportCardTabState extends State<ParentReportCardTab> {
  bool _isLoading = true;
  String? _errorMessage;
  ReportCardResponse? _reportCard;
  int _selectedExamId = 1;

  @override
  void initState() {
    super.initState();
    _fetchReportCard();
  }

  @override
  void didUpdateWidget(covariant ParentReportCardTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.enrollmentId != widget.enrollmentId) {
      _fetchReportCard();
    }
  }

  Future<void> _fetchReportCard() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final apiClient = context.read<ApiClient>();
    try {
      final response = await apiClient.get(
        ApiEndpoints.parentReportCard,
        queryParams: {
          'enrollment_id': widget.enrollmentId.toString(),
          'exam_id': _selectedExamId.toString(),
        },
      );

      if (response is Map<String, dynamic>) {
        setState(() {
          _reportCard = ReportCardResponse.fromJson(response);
          _isLoading = false;
        });
      } else {
        setState(() {
          _errorMessage = 'Invalid report card response format.';
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

  @override
  Widget build(BuildContext context) {
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
              const Icon(Icons.school_outlined, size: 48, color: AppTheme.rose500),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _fetchReportCard,
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.emerald500),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_reportCard == null) {
      return const Center(child: Text('No academic report card found.', style: TextStyle(color: AppTheme.textMuted)));
    }

    final card = _reportCard!;
    final summary = card.summary;

    return RefreshIndicator(
      onRefresh: _fetchReportCard,
      color: AppTheme.emerald500,
      backgroundColor: AppTheme.cardBackground,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Exam Header Card
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppTheme.slate800, AppTheme.cardBackground],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.cardBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.workspace_premium_rounded, color: AppTheme.emerald500, size: 28),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            card.exam.name,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          Text(
                            'Term: ${card.exam.term ?? "Standard Term"}',
                            style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
                          ),
                        ],
                      ),
                    ),
                    // Rank Badge
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppTheme.emerald500.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AppTheme.emerald500.withOpacity(0.4)),
                      ),
                      child: Text(
                        summary.classRank,
                        style: const TextStyle(
                          color: AppTheme.emerald500,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
                const Divider(color: AppTheme.cardBorder, height: 24),

                // Overall Score Details
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildSummaryMetric(
                      label: 'Marks',
                      value: '${summary.totalObtained.toStringAsFixed(0)} / ${summary.totalMaximum.toStringAsFixed(0)}',
                      color: AppTheme.textPrimary,
                    ),
                    _buildSummaryMetric(
                      label: 'Percentage',
                      value: '${summary.percentage.toStringAsFixed(1)}%',
                      color: AppTheme.emerald500,
                    ),
                    _buildSummaryMetric(
                      label: 'Grade',
                      value: summary.letterGrade,
                      color: Colors.amberAccent,
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Subject Scorecards Header
          const Text(
            'Subject-wise Performance',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 12),

          if (card.subjects.isEmpty)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 32),
              alignment: Alignment.center,
              child: const Text('No subject marks entered for this exam yet.', style: TextStyle(color: AppTheme.textMuted)),
            )
          else
            ...card.subjects.map((sub) => _buildSubjectCard(sub)),
        ],
      ),
    );
  }

  Widget _buildSummaryMetric({required String label, required String value, required Color color}) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
        ),
      ],
    );
  }

  Widget _buildSubjectCard(SubjectScorecard sub) {
    Color gradeColor = AppTheme.emerald500;
    if (sub.isAbsent) {
      gradeColor = AppTheme.rose500;
    } else if (sub.grade == 'F') {
      gradeColor = AppTheme.rose500;
    } else if (sub.grade == 'C' || sub.grade == 'D') {
      gradeColor = AppTheme.amber500;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Row(
        children: [
          // Subject icon
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppTheme.slate800,
              borderRadius: BorderRadius.circular(10),
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.book_outlined, color: AppTheme.textMuted, size: 20),
          ),
          const SizedBox(width: 12),

          // Subject Details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  sub.subjectName,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  sub.isAbsent
                      ? 'Status: Absent'
                      : 'Obtained: ${sub.marksObtained.toStringAsFixed(1)} / ${sub.maximumMarks.toStringAsFixed(1)}',
                  style: TextStyle(
                    fontSize: 12,
                    color: sub.isAbsent ? AppTheme.rose500 : AppTheme.textMuted,
                  ),
                ),
              ],
            ),
          ),

          // Grade Badge
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: gradeColor.withOpacity(0.12),
              shape: BoxShape.circle,
              border: Border.all(color: gradeColor, width: 1.5),
            ),
            alignment: Alignment.center,
            child: Text(
              sub.isAbsent ? 'ABS' : sub.grade,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: sub.isAbsent ? 10 : 14,
                color: gradeColor,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
