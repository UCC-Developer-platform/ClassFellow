import 'package:flutter_test/flutter_test.dart';
import '../lib/models/user_session.dart';
import '../lib/models/teacher_models.dart';
import '../lib/models/parent_models.dart';

void main() {
  group('UserSession Model Tests', () {
    test('UserSession parses valid json with TEACHER role', () {
      final json = {
        'token': 'mock-token-12345',
        'user_id': 10,
        'username': 'teacher.fatima',
        'role': 'TEACHER',
        'full_name': 'Fatima Ali',
      };

      final session = UserSession.fromJson(json);
      expect(session.token, equals('mock-token-12345'));
      expect(session.userId, equals(10));
      expect(session.username, equals('teacher.fatima'));
      expect(session.role, equals('TEACHER'));
      expect(session.fullName, equals('Fatima Ali'));
      expect(session.isTeacher, isTrue);
      expect(session.isParent, isFalse);
    });

    test('UserSession parses valid json with PARENT role', () {
      final json = {
        'token': 'parent-token-67890',
        'user_id': 25,
        'username': 'parent.khan',
        'role': 'PARENT',
        'full_name': 'Tariq Khan',
      };

      final session = UserSession.fromJson(json);
      expect(session.isParent, isTrue);
      expect(session.isTeacher, isFalse);
      expect(session.toJson(), equals(json));
    });
  });

  group('Teacher Models Tests', () {
    test('TeacherAllocation parses nested json structure', () {
      final json = {
        'id': 101,
        'class_group': {
          'id': 5,
          'name': 'Grade 10',
          'section': 'A',
          'campus_name': 'Main Boys Campus',
        },
        'subject': {
          'id': 12,
          'name': 'Mathematics',
          'code': 'MATH-10',
        },
        'academic_session': {
          'id': 1,
          'name': '2025-2026',
        },
      };

      final alloc = TeacherAllocation.fromJson(json);
      expect(alloc.id, equals(101));
      expect(alloc.classGroup.name, equals('Grade 10'));
      expect(alloc.classGroup.section, equals('A'));
      expect(alloc.classGroup.campusName, equals('Main Boys Campus'));
      expect(alloc.subject.name, equals('Mathematics'));
      expect(alloc.academicSession.name, equals('2025-2026'));
    });

    test('RosterResponse parses list of students', () {
      final json = {
        'class_group_id': 5,
        'attendance_date': '2026-09-17',
        'total_students': 2,
        'roster': [
          {
            'enrollment_id': 201,
            'student_id': 501,
            'full_name': 'Ahmed Raza',
            'roll_number': '10-A-01',
            'admission_number': 'ADM-2025-001',
            'attendance_status': 'PRESENT',
          },
          {
            'enrollment_id': 202,
            'student_id': 502,
            'full_name': 'Bilal Tariq',
            'roll_number': '10-A-02',
            'admission_number': 'ADM-2025-002',
            'attendance_status': 'ABSENT',
          },
        ],
      };

      final rosterResp = RosterResponse.fromJson(json);
      expect(rosterResp.classGroupId, equals(5));
      expect(rosterResp.attendanceDate, equals('2026-09-17'));
      expect(rosterResp.totalStudents, equals(2));
      expect(rosterResp.roster.length, equals(2));
      expect(rosterResp.roster.first.fullName, equals('Ahmed Raza'));
      expect(rosterResp.roster.first.attendanceStatus, equals('PRESENT'));
      expect(rosterResp.roster.last.attendanceStatus, equals('ABSENT'));
    });
  });

  group('Parent Models Tests', () {
    test('ChildProfile parses correctly', () {
      final json = {
        'enrollment_id': 201,
        'student_id': 501,
        'full_name': 'Ahmed Raza',
        'admission_number': 'ADM-2025-001',
        'roll_number': '10-A-01',
        'class_name': 'Grade 10',
        'section': 'A',
        'campus_name': 'Main Boys Campus',
      };

      final profile = ChildProfile.fromJson(json);
      expect(profile.enrollmentId, equals(201));
      expect(profile.fullName, equals('Ahmed Raza'));
      expect(profile.className, equals('Grade 10'));
      expect(profile.section, equals('A'));
    });

    test('FeeSummaryResponse parses invoices and payments', () {
      final json = {
        'enrollment_id': 201,
        'total_billed': '15000.00',
        'total_paid': '10000.00',
        'total_outstanding': '5000.00',
        'invoices': [
          {
            'id': 1,
            'invoice_number': 'INV-2026-001',
            'month_year': '2026-09',
            'fee_category': 'Monthly Tuition',
            'total_amount': '15000.00',
            'due_date': '2026-09-10',
            'status': 'PARTIAL',
          }
        ],
        'payments': [
          {
            'id': 1,
            'receipt_number': 'REC-2026-001',
            'payment_date': '2026-09-05',
            'amount_paid': '10000.00',
            'payment_method': 'CASH',
          }
        ],
      };

      final feeSummary = FeeSummaryResponse.fromJson(json);
      expect(feeSummary.totalBilled, equals(15000.00));
      expect(feeSummary.totalPaid, equals(10000.00));
      expect(feeSummary.totalOutstanding, equals(5000.00));
      expect(feeSummary.invoices.length, equals(1));
      expect(feeSummary.invoices.first.status, equals('PARTIAL'));
      expect(feeSummary.payments.length, equals(1));
      expect(feeSummary.payments.first.receiptNumber, equals('REC-2026-001'));
    });

    test('AttendanceSummaryResponse parses monthly records and percentage', () {
      final json = {
        'enrollment_id': 201,
        'month_year': '2026-09',
        'total_days': 20,
        'present_days': 18,
        'absent_days': 1,
        'leave_days': 1,
        'late_days': 0,
        'attendance_percentage': '90.00',
        'records': [
          {
            'date': '2026-09-01',
            'status': 'PRESENT',
            'remarks': '',
          },
          {
            'date': '2026-09-02',
            'status': 'ABSENT',
            'remarks': 'Unexcused',
          }
        ],
      };

      final att = AttendanceSummaryResponse.fromJson(json);
      expect(att.totalDays, equals(20));
      expect(att.presentDays, equals(18));
      expect(att.attendancePercentage, equals(90.00));
      expect(att.records.length, equals(2));
      expect(att.records.first.status, equals('PRESENT'));
    });

    test('ReportCardResponse parses summary and subject scorecard', () {
      final json = {
        'student': {
          'id': 501,
          'full_name': 'Ahmed Raza',
          'roll_number': '10-A-01',
          'class_name': 'Grade 10',
          'section': 'A',
        },
        'exam': {
          'id': 1,
          'name': 'Mid-Term Examination 2026',
          'term': 'First Term',
        },
        'summary': {
          'total_obtained': '270.00',
          'total_maximum': '300.00',
          'percentage': '90.00',
          'letter_grade': 'A+',
          'class_rank': '1st',
        },
        'subjects': [
          {
            'subject_id': 1,
            'subject_name': 'Mathematics',
            'marks_obtained': '95.00',
            'maximum_marks': '100.00',
            'grade': 'A+',
            'is_absent': false,
            'remarks': 'Outstanding performance',
          }
        ],
      };

      final report = ReportCardResponse.fromJson(json);
      expect(report.summary.letterGrade, equals('A+'));
      expect(report.summary.classRank, equals('1st'));
      expect(report.summary.totalObtained, equals(270.00));
      expect(report.subjects.length, equals(1));
      expect(report.subjects.first.subjectName, equals('Mathematics'));
      expect(report.subjects.first.marksObtained, equals(95.00));
    });
  });
}
