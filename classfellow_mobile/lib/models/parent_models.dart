/// Models supporting Parent Portal mobile workflows.

class ChildProfile {
  final int enrollmentId;
  final int studentId;
  final String admissionNumber;
  final String firstName;
  final String lastName;
  final String fullName;
  final String urduName;
  final String gender;
  final String rollNumber;
  final String className;
  final String section;
  final String campusName;
  final String sessionName;
  final String guardianName;
  final String guardianPhone;

  const ChildProfile({
    required this.enrollmentId,
    required this.studentId,
    required this.admissionNumber,
    required this.firstName,
    required this.lastName,
    required this.fullName,
    required this.urduName,
    required this.gender,
    required this.rollNumber,
    required this.className,
    required this.section,
    required this.campusName,
    required this.sessionName,
    required this.guardianName,
    required this.guardianPhone,
  });

  String get subtitle => '$className - $section ($campusName)';

  factory ChildProfile.fromJson(Map<String, dynamic> json) {
    return ChildProfile(
      enrollmentId: json['enrollment_id'] as int? ?? 0,
      studentId: json['student_id'] as int? ?? 0,
      admissionNumber: json['admission_number'] as String? ?? '',
      firstName: json['first_name'] as String? ?? '',
      lastName: json['last_name'] as String? ?? '',
      fullName: json['full_name'] as String? ?? '',
      urduName: json['urdu_name'] as String? ?? '',
      gender: json['gender'] as String? ?? 'Male',
      rollNumber: json['roll_number'] as String? ?? '',
      className: json['class_name'] as String? ?? '',
      section: json['section'] as String? ?? '',
      campusName: json['campus_name'] as String? ?? 'Main Campus',
      sessionName: json['session_name'] as String? ?? '',
      guardianName: json['guardian_name'] as String? ?? '',
      guardianPhone: json['guardian_phone'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'enrollment_id': enrollmentId,
        'student_id': studentId,
        'admission_number': admissionNumber,
        'first_name': firstName,
        'last_name': lastName,
        'full_name': fullName,
        'urdu_name': urduName,
        'gender': gender,
        'roll_number': rollNumber,
        'class_name': className,
        'section': section,
        'campus_name': campusName,
        'session_name': sessionName,
        'guardian_name': guardianName,
        'guardian_phone': guardianPhone,
      };
}

class InvoiceItem {
  final String head;
  final String amount;

  const InvoiceItem({required this.head, required this.amount});

  factory InvoiceItem.fromJson(Map<String, dynamic> json) {
    return InvoiceItem(
      head: json['head'] as String? ?? '',
      amount: json['amount'] as String? ?? '0.00',
    );
  }
}

class FeeInvoiceRecord {
  final int invoiceId;
  final String monthYear;
  final String issueDate;
  final String dueDate;
  final String validUntil;
  final String totalPayable;
  final String discountAmount;
  final String netDue;
  final String paidAmount;
  final String balance;
  final bool isPaid;
  final List<InvoiceItem> items;

  const FeeInvoiceRecord({
    required this.invoiceId,
    required this.monthYear,
    required this.issueDate,
    required this.dueDate,
    required this.validUntil,
    required this.totalPayable,
    required this.discountAmount,
    required this.netDue,
    required this.paidAmount,
    required this.balance,
    required this.isPaid,
    required this.items,
  });

  factory FeeInvoiceRecord.fromJson(Map<String, dynamic> json) {
    final list = json['items'] as List<dynamic>? ?? [];
    return FeeInvoiceRecord(
      invoiceId: json['invoice_id'] as int? ?? 0,
      monthYear: json['month_year'] as String? ?? '',
      issueDate: json['issue_date'] as String? ?? '',
      dueDate: json['due_date'] as String? ?? '',
      validUntil: json['valid_until'] as String? ?? '',
      totalPayable: json['total_payable'] as String? ?? '0.00',
      discountAmount: json['discount_amount'] as String? ?? '0.00',
      netDue: json['net_due'] as String? ?? '0.00',
      paidAmount: json['paid_amount'] as String? ?? '0.00',
      balance: json['balance'] as String? ?? '0.00',
      isPaid: json['is_paid'] as bool? ?? false,
      items: list.map((e) => InvoiceItem.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }
}

class PaymentReceiptRecord {
  final String receiptNumber;
  final String amount;
  final String paymentDate;
  final String paymentMethod;
  final int invoiceId;
  final String monthYear;

  const PaymentReceiptRecord({
    required this.receiptNumber,
    required this.amount,
    required this.paymentDate,
    required this.paymentMethod,
    required this.invoiceId,
    required this.monthYear,
  });

  factory PaymentReceiptRecord.fromJson(Map<String, dynamic> json) {
    return PaymentReceiptRecord(
      receiptNumber: json['receipt_number'] as String? ?? '',
      amount: json['amount'] as String? ?? '0.00',
      paymentDate: json['payment_date'] as String? ?? '',
      paymentMethod: json['payment_method'] as String? ?? '',
      invoiceId: json['invoice_id'] as int? ?? 0,
      monthYear: json['month_year'] as String? ?? '',
    );
  }
}

class FeeSummaryResponse {
  final String totalBilled;
  final String totalPaid;
  final String totalOutstanding;
  final List<FeeInvoiceRecord> invoices;
  final List<PaymentReceiptRecord> payments;

  const FeeSummaryResponse({
    required this.totalBilled,
    required this.totalPaid,
    required this.totalOutstanding,
    required this.invoices,
    required this.payments,
  });

  factory FeeSummaryResponse.fromJson(Map<String, dynamic> json) {
    final invList = json['invoices'] as List<dynamic>? ?? [];
    final payList = json['payments'] as List<dynamic>? ?? [];
    return FeeSummaryResponse(
      totalBilled: json['total_billed'] as String? ?? '0.00',
      totalPaid: json['total_paid'] as String? ?? '0.00',
      totalOutstanding: json['total_outstanding'] as String? ?? '0.00',
      invoices: invList.map((e) => FeeInvoiceRecord.fromJson(e as Map<String, dynamic>)).toList(),
      payments: payList.map((e) => PaymentReceiptRecord.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }
}

class AttendanceRecordItem {
  final String date;
  final String status;
  final String reasonNote;

  const AttendanceRecordItem({
    required this.date,
    required this.status,
    required this.reasonNote,
  });

  factory AttendanceRecordItem.fromJson(Map<String, dynamic> json) {
    return AttendanceRecordItem(
      date: json['date'] as String? ?? '',
      status: json['status'] as String? ?? '',
      reasonNote: json['reason_note'] as String? ?? '',
    );
  }
}

class AttendanceSummaryResponse {
  final int totalDays;
  final int presentDays;
  final int absentDays;
  final int leaveDays;
  final int lateDays;
  final String attendancePercentage;
  final List<AttendanceRecordItem> records;

  const AttendanceSummaryResponse({
    required this.totalDays,
    required this.presentDays,
    required this.absentDays,
    required this.leaveDays,
    required this.lateDays,
    required this.attendancePercentage,
    required this.records,
  });

  factory AttendanceSummaryResponse.fromJson(Map<String, dynamic> json) {
    final list = json['records'] as List<dynamic>? ?? [];
    return AttendanceSummaryResponse(
      totalDays: json['total_days'] as int? ?? 0,
      presentDays: json['present_days'] as int? ?? 0,
      absentDays: json['absent_days'] as int? ?? 0,
      leaveDays: json['leave_days'] as int? ?? 0,
      lateDays: json['late_days'] as int? ?? 0,
      attendancePercentage: json['attendance_percentage'] as String? ?? '0.0',
      records: list.map((e) => AttendanceRecordItem.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }
}

class SubjectScorecard {
  final String subjectName;
  final String subjectCode;
  final String maximumMarks;
  final String passingMarks;
  final String marksObtained;
  final bool isAbsent;
  final bool isPassed;
  final String remarks;

  const SubjectScorecard({
    required this.subjectName,
    required this.subjectCode,
    required this.maximumMarks,
    required this.passingMarks,
    required this.marksObtained,
    required this.isAbsent,
    required this.isPassed,
    required this.remarks,
  });

  factory SubjectScorecard.fromJson(Map<String, dynamic> json) {
    return SubjectScorecard(
      subjectName: json['subject_name'] as String? ?? '',
      subjectCode: json['subject_code'] as String? ?? '',
      maximumMarks: json['maximum_marks'] as String? ?? '0.00',
      passingMarks: json['passing_marks'] as String? ?? '0.00',
      marksObtained: json['marks_obtained'] as String? ?? '0.00',
      isAbsent: json['is_absent'] as bool? ?? false,
      isPassed: json['is_passed'] as bool? ?? false,
      remarks: json['remarks'] as String? ?? '',
    );
  }
}

class ReportCardResponse {
  final String studentName;
  final String examName;
  final String examTerm;
  final String sessionName;
  final String totalObtained;
  final String totalMaximum;
  final String percentage;
  final String letterGrade;
  final dynamic classRank;
  final List<SubjectScorecard> subjects;

  const ReportCardResponse({
    required this.studentName,
    required this.examName,
    required this.examTerm,
    required this.sessionName,
    required this.totalObtained,
    required this.totalMaximum,
    required this.percentage,
    required this.letterGrade,
    required this.classRank,
    required this.subjects,
  });

  factory ReportCardResponse.fromJson(Map<String, dynamic> json) {
    final stu = json['student'] as Map<String, dynamic>? ?? {};
    final exam = json['exam'] as Map<String, dynamic>? ?? {};
    final summary = json['summary'] as Map<String, dynamic>? ?? {};
    final subList = json['subjects'] as List<dynamic>? ?? [];

    return ReportCardResponse(
      studentName: stu['full_name'] as String? ?? '',
      examName: exam['name'] as String? ?? '',
      examTerm: exam['term'] as String? ?? '',
      sessionName: exam['session_name'] as String? ?? '',
      totalObtained: summary['total_obtained'] as String? ?? '0.00',
      totalMaximum: summary['total_maximum'] as String? ?? '0.00',
      percentage: summary['percentage'] as String? ?? '0.00',
      letterGrade: summary['letter_grade'] as String? ?? 'N/A',
      classRank: summary['class_rank'] ?? 'N/A',
      subjects: subList.map((e) => SubjectScorecard.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }
}
